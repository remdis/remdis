import sys, os
import time

from google.cloud import speech as gspeech
import MeCab

import queue
import threading
import base64

from base import RemdisModule, RemdisUpdateType

STREAMING_LIMIT = 240  # 4 minutes

def get_text_increment(module, new_text, tagger):
    iu_buffer = []
    
    # 認識結果をトークンへ分割
    new_text = tagger.parse(new_text)
    tokens = new_text.strip().split(" ")

    # トークンがない場合は終了
    if tokens == [""]:
        return iu_buffer, []

    new_tokens = []
    iu_idx = 0
    token_idx = 0
    while token_idx < len(tokens):
        # 過去の音声認識結果と新しい音声認識結果を比較
        if iu_idx >= len(module.current_output):
            new_tokens.append(tokens[token_idx])
            token_idx += 1
        else:
            current_iu = module.current_output[iu_idx]
            iu_idx += 1
            if tokens[token_idx] == current_iu['body']:
                token_idx += 1
            else:
                # 変更があったIUをREVOKEに設定し格納
                current_iu['update_type'] = RemdisUpdateType.REVOKE
                iu_buffer.append(current_iu)

    # current_outputに新しい音声認識結果のIUを格納
    module.current_output = [iu for iu in module.current_output if iu['update_type'] is not RemdisUpdateType.REVOKE]

    return iu_buffer, new_tokens

class ASR(RemdisModule):
    def __init__(self,
                 pub_exchanges=['asr'],
                 sub_exchanges=['ain']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)

        self.buff_size = self.config['ASR']['buff_size']
        self.audio_buffer = queue.Queue() # 受信用キュー

        # 一つ前のステップの音声認識結果
        self.current_output = [] 

        # ASR用の変数
        self.language = self.config['ASR']['language']
        self.nchunks = self.config['ASR']['chunk_size']
        self.rate = self.config['ASR']['sample_rate']

        self.client = None
        self.streaming_config = None
        self.responses = []

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.config['ASR']['json_key']

        # ASR リスタート用の変数
        self.asr_start_time = 0.0
        self.asr_init()
        
        self.tagger = MeCab.Tagger("-Owakati")

        self._is_running = True
        self.resume_asr = False

    def run(self):
        # メッセージ受信スレッド
        t1 = threading.Thread(target=self.listen_loop)
        # 音声認識・メッセージ送信スレッド
        t2 = threading.Thread(target=self.produce_predictions_loop)

        # スレッド実行
        t1.start()
        t2.start()

    def listen_loop(self):
        self.subscribe('ain', self.callback)

    def produce_predictions_loop(self):
        while self._is_running:                
            # 逐次音声認識結果の取得
            requests = (
                gspeech.StreamingRecognizeRequest(audio_content=content)
                for content in self._generator()
            )

            if self.resume_asr == True:
                sys.stderr.write('Resume: ASR\n')
                self.asr_init()
            
            self.responses = self.client.streaming_recognize(
                self.streaming_config, requests
            )
            
            # 音声認識結果の解析とメッセージの発出
            for response in self.responses:
                # Google Cloud Speech-to-Textの結果を格納
                p = self._extract_results(response)

                if p:
                    current_text = p['text']

                    # iu_buffer: REVOKEしたIUを格納した送信用IUバッファ
                    # new_tokens: 新しい音声認識結果のトークン系列
                    iu_buffer, new_tokens = get_text_increment(self,
                                                               current_text,
                                                               self.tagger)

                    # 発出するトークンがない場合の処理
                    if len(new_tokens) == 0:
                        if not p['is_final']:
                            continue
                        else:
                            # f (is_final)がTrueの時は空のIUをCOMMITで作成
                            output_iu = self.createIU_ASR('', [p['stability'], p['confidence']])
                            output_iu['update_type'] = RemdisUpdateType.COMMIT
                            #self.current_output = []
                            # 送信用バッファに格納
                            iu_buffer.append(output_iu)

                    # 発出するトークンが存在する場合の処理        
                    for i, token in enumerate(new_tokens):
                        output_iu = self.createIU_ASR(token, [0.0, 0.99])
                        eou = p['is_final'] and i == len(new_tokens) - 1
                        if eou:
                            # 発話終端であればCOMMITに設定
                            output_iu['update_type'] = RemdisUpdateType.COMMIT
                        else:
                            self.current_output.append(output_iu)

                        iu_buffer.append(output_iu)

                    # 送信用バッファに格納したIUを発出
                    for snd_iu in iu_buffer:
                        self.printIU(snd_iu)
                        self.publish(snd_iu, 'asr')

    # ASRモジュール用のIU作成関数 (信頼スコアなどを格納)
    def createIU_ASR(self, token, asr_result):
        iu = self.createIU(token, 'asr', RemdisUpdateType.ADD)
        iu['stability'] = asr_result[0]
        iu['confidence'] = asr_result[1]
        return iu
        
    # バッファに溜まった音声波形を結合し返却するgenerator
    def _generator(self):
        while self._is_running:
            # ASRがタイムアウトしそうな場合は再起動
            current_time = time.time()
            proc_time = current_time - self.asr_start_time
            if proc_time >= STREAMING_LIMIT:
                self.resume_asr = True
                break
            
            # 最初のデータの取得
            chunk = self.audio_buffer.get()
            # 何も送られていなければ処理を終了
            if chunk is None:
                return
            data = [chunk]

            # データがバッファに残っていれば全て取得
            while True:
                try:
                    chunk = self.audio_buffer.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            # 取得されたデータを結合し返却
            yield b"".join(data)

    def _extract_results(self, response):
        predictions = {}
        text = None
        stability = 0.0
        confidence = 0.0
        final = False
        
        # Google Cloud Speech-to-Text APIのレスポンスの解析
        if len(response.results) != 0:
            result = response.results[-1] # 途中結果の部分
            # 2024.1よりstabilityの値でis_finalを判定するように変更
            if result.stability < 0.8:
                conc_trans = ''
                # 現時刻までのすべての音声認識結果を結合
                for elm in response.results:
                    conc_trans += elm.alternatives[0].transcript
                    
                # transcript: 書き起こし結果
                # stability: 結果の安定性
                # confidence: 信頼スコア
                # is_final: 発話終端であればTrue
                predictions = {
                    'text': conc_trans,
                    'stability': result.stability,
                    'confidence': result.alternatives[0].confidence,
                    'is_final': result.is_final,
                }
            else:
                predictions = predictions = {
                    'text': '',
                    'stability': result.stability,
                    'confidence': result.alternatives[0].confidence,
                    'is_final': True,
                }
            
        return predictions
                    
    def asr_init(self):
        sys.stderr.write('Start: Streaming ASR\n')
        self.asr_start_time = time.time()
        self.resume_asr = False
        
        # Google Cloud Speech-to-Textクライアントのインスタンス構築
        self.client = gspeech.SpeechClient()
        config = gspeech.RecognitionConfig(
            encoding=gspeech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language,
        )
        # ストリーミング音声認識用の設定
        self.streaming_config = gspeech.StreamingRecognitionConfig(
            config=config, interim_results=True,
            enable_voice_activity_events=True
        )

    # メッセージ受信用コールバック関数
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.audio_buffer.put(base64.b64decode(in_msg['body'].encode()))

def main():
    asr = ASR()
    asr.run()

if __name__ == '__main__':
    main()

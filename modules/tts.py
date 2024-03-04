import sys, os
import numpy
import queue

import time

import threading
import base64
import librosa

from ttslearn.pretrained import create_tts_engine
import pyopenjtalk
from base import RemdisModule, RemdisUpdateType

import torch
device = torch.device("cpu")

class TTS(RemdisModule):
    def __init__(self, 
                 pub_exchanges=['tts'],
                 sub_exchanges=['dialogue']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)
        
        self.rate = self.config['TTS']['sample_rate']
        self.frame_length = self.config['TTS']['frame_length']
        self.send_interval = self.config['TTS']['send_interval']
        self.sample_width = self.config['TTS']['sample_width']
        self.chunk_size = round(self.frame_length * self.rate)

        self.input_iu_buffer = queue.Queue()
        self.output_iu_buffer = queue.Queue()
        self.engine_name = self.config['TTS']['engine_name']
        self.model_name = self.config['TTS']['model_name']
        if self.engine_name == 'ttslearn':
            self.engine = create_tts_engine(self.model_name,
                                            device=device)
        
        self.is_revoked = False
        self._is_running = True

    def run(self):
        # メッセージ受信スレッド
        t1 = threading.Thread(target=self.listen_loop)
        # 音声合成処理スレッド
        t2 = threading.Thread(target=self.synthesis_loop)
        # メッセージ送信スレッド
        t3 = threading.Thread(target=self.send_loop)

        # スレッド実行
        t1.start()
        t2.start()
        t3.start()

        t1.join()
        t2.join()
        t3.join()

    def listen_loop(self):
        self.subscribe('dialogue', self.callback)

    def send_loop(self):
        # 音声データをチャンクごとに送信
        while True:
            # REVOKEされた場合は送信を停止 (= ユーザ割り込み時の処理)
            if self.is_revoked:
                self.output_iu_buffer = queue.Queue()
                self.send_commitIU('tts')
                
            snd_iu = self.output_iu_buffer.get(block=True)
            self.publish(snd_iu, 'tts')

            # チャンクの間隔ごとに送信を実行(音が切れるので少し早い間隔で送信)
            time.sleep(self.send_interval)

            # システム発話終端まで送信した場合の処理
            if snd_iu['update_type'] == RemdisUpdateType.COMMIT:
                self.send_commitIU('tts')

    def synthesis_loop(self):
        while True:
            if self.is_revoked:
                self.input_iu_buffer = queue.Queue()

            # 入力バッファから受信したIUを取得
            in_msg = self.input_iu_buffer.get(block=True)
            output_text = in_msg['body']
            tgt_id = in_msg['id']
            update_type = in_msg['update_type']

            x = numpy.array([])
            sr = 0
            sleep_time = 0

            if output_text != '':
                # 音声合成
                if self.engine_name == 'ttslearn':
                    x, sr = self.engine.tts(output_text)
                elif self.engine_name == 'openjtalk':
                    x, sr = pyopenjtalk.tts(output_text, half_tone=-3.0)
                else:
                    sys.stderr.write('Currently, ttslearn and openjtalk are acceptable as a tts engine.')

                # MMDAgent-EXの仕様に合わせて音声をダウンサンプリング
                x = librosa.resample(x.astype(numpy.float32),
                                     orig_sr=sr,
                                     target_sr=self.rate)
                
                # チャンクに分割して出力バッファに格納
                t = 0
                while t <= len(x):
                    chunk = x[t:t+self.chunk_size]
                    chunk = base64.b64encode(chunk.astype(numpy.int16).tobytes()).decode('utf-8')
                    snd_iu = self.createIU(chunk, 'tts',
                                           update_type)
                    snd_iu['data_type'] = 'audio'
                    self.output_iu_buffer.put(snd_iu)
                    t += self.chunk_size
            else:
                # テキストがない場合も処理を実施
                x = numpy.zeros(self.chunk_size)
                chunk = base64.b64encode(x.astype(numpy.int16).tobytes()).decode('utf-8')
                snd_iu = self.createIU(chunk, 'tts',
                                       update_type)
                snd_iu['data_type'] = 'audio'
                self.output_iu_buffer.put(snd_iu)

    # 発話終了時のメッセージ送信関数
    def send_commitIU(self, channel):
        snd_iu = self.createIU('', channel,
                               RemdisUpdateType.COMMIT)
        snd_iu['data_type'] = 'audio'
        self.printIU(snd_iu)
        self.publish(snd_iu, channel)

    # メッセージ受信用コールバック関数
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.printIU(in_msg)
        
        # システム発話のupdate_typeを監視
        if in_msg['update_type'] == RemdisUpdateType.REVOKE:
            self.is_revoked = True
        else:
            self.input_iu_buffer.put(in_msg)
            self.is_revoked = False

def main():
    tts = TTS()
    tts.run()

if __name__ == '__main__':
    main()

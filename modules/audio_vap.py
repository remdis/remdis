import sys, os
import time
import numpy
import queue

import threading
import base64, copy
import librosa, pysptk

import torch
import torch.nn as nn
from _audio_vap.VAP import VAP
from _audio_vap.encoder import EncoderCPC
from _audio_vap.modules import TransformerStereo

from scipy.io.wavfile import write

from base import RemdisModule, RemdisUpdateType

from vap.utils.audio import load_waveform

# GPUの設定
if sys.platform == 'darwin':
    # Mac
    device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
else:
    # Windows/Linux
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') 

class Audio_VAP(RemdisModule):
    def __init__(self, 
                 pub_exchanges=['vap', 'score'],
                 sub_exchanges=['ain', 'tts']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)

        # VAP用変数
        self.model_name = self.config['VAP']['model_filename']
        self.buffer_length = self.config['VAP']['buffer_length']
        self.threshold = self.config['VAP']['threshold']
        self.sample_rate = self.config['TTS']['sample_rate']
        self.buffer_size = int(self.buffer_length * self.sample_rate)
        self.tts_frame_length = self.config['TTS']['frame_length']

        self.us_audio_buffer = numpy.zeros(self.buffer_size,
                                           dtype=numpy.float32)
        self.ss_audio_buffer = numpy.zeros(self.buffer_size,
                                           dtype=numpy.float32)

        self.ss_msg_buffer = queue.Queue()
        self.prev_event = None
        
        self._is_running = True

    def run(self):
        # ユーザ発話受信スレッド
        t1 = threading.Thread(target=self.us_listen_loop)
        # システム発話受信スレッド
        t2 = threading.Thread(target=self.ss_listen_loop)
        # システム発話構築スレッド
        t3 = threading.Thread(target=self.ss_buffering_loop)
        # VAP実行スレッド
        t4 = threading.Thread(target=self.vap_loop)

        # スレッド実行
        t1.start()
        t2.start()
        t3.start()
        t4.start()

        t1.join()
        t2.join()
        t3.join()
        t4.join()
                
    def us_listen_loop(self):
        self.subscribe('ain', self.us_callback)

    def ss_listen_loop(self):
        self.subscribe('tts', self.ss_callback)

    def ss_buffering_loop(self):        
        delay_time = 0.0
        while True:
            start_time = time.time()
            try:
                # システム発話がキューにあったら全てバッファに格納
                chunk = self.ss_msg_buffer.get(block=False)
                self.ss_audio_buffer = self.shift_buffer(self.ss_audio_buffer, chunk)
            except:
                # ない場合は遅延時間とTTSのフレーム長を合わせた分の無音を格納
                chunk_time = delay_time + self.tts_frame_length
                chunk_size = int(chunk_time * self.sample_rate)
                chunk = numpy.zeros(chunk_size)
                self.ss_audio_buffer = self.shift_buffer(self.ss_audio_buffer, chunk)
                delay_time = 0.0

            # TTSのフレーム長に同期してループ
            proc_time = time.time() - start_time
            sleep_time = self.tts_frame_length - proc_time
            time.sleep(sleep_time)

            delay_time += proc_time
                    
    def vap_loop(self):
        # VAPモデルの読み込み
        encoder = EncoderCPC()
        transformer = TransformerStereo()
        model = VAP(encoder, transformer)
        ckpt = torch.load(self.model_name, map_location=device)['state_dict']
        restored_ckpt = {}
        for k,v in ckpt.items():
            restored_ckpt[k.replace('model.', '')] = v
        model.load_state_dict(restored_ckpt)
        model.eval()
        model.to(device)
        sys.stderr.write('Load VAP model: %s\n' % (self.model_name))
        sys.stderr.write('Device: %s\n' % (device))
        
        s_threshold = self.threshold
        u_threshold = 1 - self.threshold
        while True:
            # 両話者のデータを結合してバッチを作成
            ss_audio = torch.Tensor(self.ss_audio_buffer)
            us_audio = torch.Tensor(self.us_audio_buffer)
            input_audio = torch.stack((ss_audio, us_audio))
            input_audio = input_audio.unsqueeze(0)
            batch = torch.Tensor(input_audio)
            batch = batch.to(device)

            # 推論
            out = model.probs(batch)
            #print(out['vad'].shape,
            #      out['p_now'].shape,
            #      out['p_future'].shape,
            #      out['probs'].shape,
            #      out['H'].shape)

            # 結果の取得
            p_ns = out['p_now'][0, :].cpu()
            p_fs = out['p_future'][0, :].cpu()
            vad_result = out['vad'][0, :].cpu()

            # 最終フレームの結果を判定に利用
            score_n = p_ns[-1].item()
            score_f = p_fs[-1].item()
            score_v = vad_result[-1]

            # イベントの判定
            event = None
            if score_n >= self.threshold and score_f >= self.threshold:
                event = 'SYSTEM_TAKE_TURN'
            if score_n < self.threshold and score_f < self.threshold:
                event = 'USER_TAKE_TURN'

            # メッセージの発出
            # 可視化用スコア
            score = {'p_now': score_n,
                     'p_future': score_f}
            snd_iu = self.createIU(score, 'score',
                                   RemdisUpdateType.ADD)
            self.publish(snd_iu, 'score')

            # 変化があった時のみイベントを発出
            if event and event != self.prev_event:
                snd_iu = self.createIU(event, 'vap',
                                       RemdisUpdateType.ADD)
                print('n:%.3f, f:%.3f, %s' % (score_n,
                                              score_f,
                                              event))
                self.publish(snd_iu, 'vap')
                self.prev_event = event
            else:
                print('n:%.3f, f:%.3f' % (score_n,
                                          score_f))
            
    def us_callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        chunk = base64.b64decode(in_msg['body'].encode())
        chunk = numpy.frombuffer(chunk, dtype=numpy.int16)
        # 振幅を-1.0から1.0の範囲に正規化
        chunk = chunk.astype(numpy.float32) / 32768.0
        chunk = chunk.astype(numpy.float32)
        self.us_audio_buffer = self.shift_buffer(self.us_audio_buffer, chunk)

    def ss_callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        chunk = base64.b64decode(in_msg['body'].encode())
        chunk = numpy.frombuffer(chunk, dtype=numpy.int16)
         # 振幅を-1.0から1.0の範囲に正規化
        chunk = chunk.astype(numpy.float32) / 32768.0
        if in_msg['update_type'] == RemdisUpdateType.ADD:
            self.ss_msg_buffer.put(chunk)

    # バッファ格納用関数
    def shift_buffer(self, in_buffer, chunk):
        chunk_size = len(chunk)
        in_buffer[:-chunk_size] = in_buffer[chunk_size:]
        in_buffer[-chunk_size:] = chunk
        return in_buffer

    # デバッグ用音声保存関数
    def save_wave(self, in_buffer, wav_filename='tmp.wav'):
        in_buffer = in_buffer.to('cpu').detach().numpy().copy()
        in_buffer = in_buffer * 32768
        in_buffer = in_buffer.astype(numpy.int16).T
        write(wav_filename, self.sample_rate, in_buffer)

    # 音声波形のパワーを計算する関数
    def calc_pow(self, segment):
        return numpy.log(numpy.mean(segment**2))

def main():
    vap = Audio_VAP()
    vap.run()

if __name__ == '__main__':
    main()

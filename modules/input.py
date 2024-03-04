import sys, os

import pyaudio
import queue
import base64

import threading

from base import RemdisModule, RemdisUpdateType

class AIN(RemdisModule):
    def __init__(self,
                 pub_exchanges=['ain']):
        super().__init__(pub_exchanges=pub_exchanges)
        
        self.frame_length = self.config['AIN']['frame_length']
        self.rate = self.config['AIN']['sample_rate']
        self.sample_width = self.config['AIN']['sample_width']
        self.num_audio_channel = self.config['AIN']['num_channel']
        self.chunk_size = round(self.frame_length * self.rate)         

        # 音声入力ストリームの宣言
        self._p = pyaudio.PyAudio()
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=self.num_audio_channel,
            rate=self.rate,
            input=True,
            output=False,
            frames_per_buffer=self.chunk_size,
            start=False,
        )
        self.stream.start_stream()

        self.is_running = True
        
    def run(self):
        # メッセージ送受信スレッド
        t1 = threading.Thread(target=self.listen_wav_loop)

        # スレッド実行
        t1.start()

    def listen_wav_loop(self):
        while self.stream.is_active():
            input_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            input_data = base64.b64encode(input_data).decode('utf-8')
            snd_iu = self.createIU(input_data, 'ain',
                                   RemdisUpdateType.ADD)
            # マイクから入力されたものをそのまま送信
            self.publish(snd_iu, 'ain')

def main():
    ain = AIN()
    ain.run()

if __name__ == '__main__':
    main()

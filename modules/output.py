import sys, os

import pyaudio
import queue
import base64

import threading

from base import RemdisModule, RemdisUpdateType

class AOUT(RemdisModule):
    def __init__(self,
                 sub_exchanges=['tts']):
        super().__init__(sub_exchanges=sub_exchanges)
        
        self.frame_length = self.config['AOUT']['frame_length']
        self.rate = self.config['AOUT']['sample_rate']
        self.sample_width = self.config['AOUT']['sample_width']
        self.channel = self.config['AOUT']['num_channel']
        self.chunk_size = round(self.frame_length * self.rate * self.sample_width)

        self.input_iu_buffer = queue.Queue()

        # 音声再生ストリームの宣言
        self._p = pyaudio.PyAudio()
        
        device_index = None
        if device_index is None:
            device_index = self._p.get_default_output_device_info()['index']
        self.device_index = device_index
        
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=self.channel,
            rate=self.rate,
            input=False,
            output=True,
            output_device_index=self.device_index,
        )
        self.stream.start_stream()

        self.is_running = True

    def run(self):
        # メッセージ受信スレッド
        t1 = threading.Thread(target=self.listen_tts_loop)
        # 音声再生用スレッド
        t2 = threading.Thread(target=self.play_wav_loop)

        # スレッド実行
        t1.start()
        t2.start()
        
    def listen_tts_loop(self):
        self.subscribe('tts', self.callback)

    def play_wav_loop(self):
        while True:
            in_msg = self.input_iu_buffer.get(block=True)
            
            # 音声再生処理
            t = 0
            output_wav = base64.b64decode(in_msg['body'].encode())
            while t <= len(output_wav):
                output_segment = output_wav[t:t+self.chunk_size]
                self.stream.write(output_segment)
                t += self.chunk_size

    # メッセージ受信用コールバック関数
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.input_iu_buffer.put(in_msg)
            
def main():
    aout = AOUT()
    aout.run()

if __name__ == '__main__':
    main()

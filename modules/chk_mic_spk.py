import sys, os
import numpy
import queue

import time

import threading
import base64
import librosa

from base import RemdisModule, RemdisUpdateType

from matplotlib import pyplot as plt
from matplotlib import animation

class ChkMicSpk(RemdisModule):
    def __init__(self, 
                 sub_exchanges=['ain'],
                 pub_exchanges=['tts']):
        super().__init__(sub_exchanges=sub_exchanges,
                         pub_exchanges=pub_exchanges)
        
        self.input_audio_buffer = queue.Queue()
        self._is_running = True

    def run(self):
        # メッセージ受信スレッド
        t1 = threading.Thread(target=self.listen_loop)

        # スレッド実行
        t1.start()
        
        self.plot_and_publish_loop()
        t1.join()

    def listen_loop(self):
        self.subscribe('ain', self.callback)

    # メッセージ受信用コールバック関数
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        chunk = base64.b64decode(in_msg['body'].encode())
        self.input_audio_buffer.put(chunk)

    def plot_and_publish_loop(self):
        while True:
            wait_start = time.time()
            chunk = self.input_audio_buffer.get()
            data = numpy.frombuffer(chunk, dtype=numpy.int16)

            chunk = base64.b64encode(chunk).decode('utf-8')
            snd_iu = self.createIU(chunk, 'tts',
                                   RemdisUpdateType.ADD)
            snd_iu['data_type'] = 'audio'
            self.publish(snd_iu, 'tts')

def main():
    cms = ChkMicSpk()
    cms.run()

if __name__ == '__main__':
    main()

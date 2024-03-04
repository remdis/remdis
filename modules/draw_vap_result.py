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

class DrawScore(RemdisModule):
    def __init__(self, 
                 sub_exchanges=['score']):
        super().__init__(sub_exchanges=sub_exchanges)
        
        self.input_iu_buffer = queue.Queue()
        self._is_running = True

    def run(self):
        # メッセージ受信スレッド
        t1 = threading.Thread(target=self.listen_loop)

        # スレッド実行
        t1.start()

        self.realtime_plot()
        
        t1.join()

    def listen_loop(self):
        self.subscribe('score', self.callback)

    # メッセージ受信用コールバック関数
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.input_iu_buffer.put(in_msg)

    def realtime_plot(self):
        fig, ax = plt.subplots(2, 1, figsize=(8, 4))
        x = numpy.arange(0, 100)
        y_n = numpy.zeros(100)
        y_f = numpy.zeros(100)
        
        while True:
            ax[0].cla()
            ax[1].cla()
            wait_start = time.time()
            in_msg = self.input_iu_buffer.get()
            score = in_msg['body']
            score_p = score['p_now']
            score_f = score['p_future']
            wait_time = time.time() - wait_start
            for i in range(len(y_n)-1):
                y_n[i] = y_n[i+1]
                y_f[i] = y_f[i+1]
            y_n[-1] = score_p
            y_f[-1] = score_f

            ax[0].fill_between(x, y1=y_n, y2=0.5,
                               where=y_n>=0.5,
                               alpha=0.6,
                               color='b',
                               label='system')
            ax[0].fill_between(x, y1=y_n, y2=0.5,
                               where=y_n<0.5,
                               alpha=0.6,
                               color='orange',
                               label='user')

            ax[1].fill_between(x, y1=y_f, y2=0.5,
                               where=y_f>=0.5,
                               alpha=0.6,
                               color='b',
                               label='system')
            ax[1].fill_between(x, y1=y_f, y2=0.5,
                               where=y_f<0.5,
                               alpha=0.6,
                               color='orange',
                               label='user')

            ax[0].set_ylabel('$p_{now}$')
            ax[0].set_xlabel('Time')
            ax[0].plot(y_n, 'k')
            ax[0].set_ylim((0.0, 1.0))

            ax[1].set_ylabel('$p_{future}$')
            ax[1].set_xlabel('Time')
            ax[1].plot(y_f, 'k')
            ax[1].set_ylim((0.0, 1.0))
            
            plt.tight_layout()
            plt.pause(0.0001)
        
def main():
    ds = DrawScore()
    ds.run()

if __name__ == '__main__':
    main()

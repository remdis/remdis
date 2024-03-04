import threading
import queue
import time

from base import RemdisModule, RemdisUpdateType


class TimeOut(RemdisModule):
    def __init__(self, 
                 pub_exchanges=['vap'],
                 sub_exchanges=['asr', 'tts']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)
        # 設定の読み込み
        self.max_silence_time = self.config['TIME_OUT']['max_silence_time']
        self.max_timeout_num = self.config['TIME_OUT']['max_timeout_num']
        self.block_time = self.config['TIME_OUT']['block_time']

        # 最後に音声認識結果または音声合成結果を受信してからタイムアウトした回数
        self.timeout_num = 0
        
        # 最新の音声認識結果または音声合成結果のタイムスタンプおよびその更新用のロック
        self.last_utterance_timestamp = time.time()
        self.lock_for_utterance_timestamp = threading.Lock()

        # 最後にタイムアウトしたタイムスタンプ（タイムアウトによるタイムスタンプの更新をブロックするための）
        self.last_timeout_timestamp = None
        
        self.input_iu_buffer = queue.Queue()

    # メインループ
    def run(self):
        t1 = threading.Thread(target=self.listen_asr_loop)
        t2 = threading.Thread(target=self.listen_tts_loop)
        t3 = threading.Thread(target=self.update_utterance_timestamp)
        t4 = threading.Thread(target=self.check_timeout)

        t1.start()
        t2.start()
        t3.start()
        t4.start()

    # 音声認識結果受信用のコールバックを登録
    def listen_asr_loop(self):
        self.subscribe('asr', self.callback_asr)

    # 音声合成結果受信用のコールバックを登録
    def listen_tts_loop(self):
        self.subscribe('tts', self.callback_tts)

    # 最新の音声認識結果のタイムスタンプを更新
    def update_utterance_timestamp(self):
        while True:
            iu = self.input_iu_buffer.get()

            with self.lock_for_utterance_timestamp:
                self.last_utterance_timestamp = iu['timestamp']
                self.timeout_num = 0
    
    # 音声認識結果のタイムスタンプが更新されていない場合にタイムアウト
    def check_timeout(self):
        while True:
            time.sleep(1.0)

            with self.lock_for_utterance_timestamp:
                if self.timeout_num >= self.max_timeout_num:
                    continue

                current_time = time.time()

                # タイムアウトしたらシステム発話を開始
                # タイムアウト回数が増えるごとにタイムアウト時間を延長
                if current_time - self.last_utterance_timestamp > self.max_silence_time * (self.timeout_num + 1):
                    self.timeout_num += 1
                    self.last_utterance_timestamp = current_time
                    self.last_timeout_timestamp = current_time
                    self.send_system_take_turn()
    
    # システム発話を開始させるIUを送信
    def send_system_take_turn(self):
        snd_iu = self.createIU('SYSTEM_TAKE_TURN', 'str', RemdisUpdateType.COMMIT)
        self.printIU(snd_iu)
        self.publish(snd_iu, 'vap')
                            
    # 音声認識結果受信用のコールバック
    def callback_asr(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.input_iu_buffer.put(in_msg)
            
    # 音声合成結果受信用のコールバック
    def callback_tts(self, ch, method, properties, in_msg):
        current_time = time.time()
        if self.last_timeout_timestamp is not None and current_time - self.last_timeout_timestamp < self.block_time:
            return

        in_msg = self.parse_msg(in_msg)
        self.input_iu_buffer.put(in_msg)

    # デバッグ用にログを出力
    def log(self, *args, **kwargs):
        print(f"[{time.time():.5f}]", *args, flush=True, **kwargs)


def main():
    time_out = TimeOut()
    time_out.run()


if __name__ == '__main__':
    main()

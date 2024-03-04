import sys
import json
import threading
import queue
import time
import re

import openai

from base import RemdisModule, RemdisUtil, RemdisUpdateType
from base import MMDAgentEXLabel
import prompt.util as prompt_util

class TextVAP(RemdisModule):
    def __init__(self, 
                 pub_exchanges=['bc', 'vap', 'emo_act'],
                 sub_exchanges=['asr']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)

        # ChatGPTの設定
        openai.api_key = self.config['ChatGPT']['api_key']
        self.model = self.config['ChatGPT']['text_vap_model']
        self.max_tokens = self.config['ChatGPT']['max_tokens']
        self.prompts = prompt_util.load_prompts(self.config['ChatGPT']['prompts'])

        # テキストVAPの設定
        self.min_text_vap_threshold = self.config['TEXT_VAP']['min_text_vap_threshold']
        self.text_vap_interval = self.config['TEXT_VAP']['text_vap_interval']

        # バックチャネルの送信回数を制限するための変数
        self.max_verbal_backchannel_num = self.config['TEXT_VAP']['max_verbal_backchannel_num']
        self.max_nonverbal_backchannel_num = self.config['TEXT_VAP']['max_nonverbal_backchannel_num']
        self.backchannel_sent_lock = threading.Lock()
        self.sent_verbal_backchannel_counter = 0
        self.last_verbal_backchannel_timestamp = -1
        self.sent_nonverbal_backchannel_counter = 0
        self.last_nonverbal_backchannel_timestamp = -1
        
        # ユーザ発話を聞き取り中かどうかのフラグ
        self.is_listening = False

        # IU処理用のバッファ
        self.input_iu_buffer = queue.Queue()
        
        # IU処理用の関数
        self.util_func = RemdisUtil()

    # メインループ
    def run(self):
        t1 = threading.Thread(target=self.listen_asr_loop)
        t2 = threading.Thread(target=self.parallel_text_vap)

        t1.start()
        t2.start()

    # 音声認識結果受信用のコールバックを登録
    def listen_asr_loop(self):
        self.subscribe('asr', self.callback_asr)

    # 随時受信される音声認識結果に対して並列にテキストVAPを実施
    def parallel_text_vap(self):
        iu_memory = []
        new_iu_count = 0

        while True:
            # ユーザ発話開始時の処理
            if len(iu_memory) == 0:
                self.is_listening = True
                self.sent_verbal_backchannel_counter = 0
                self.sent_nonverbal_backchannel_counter = 0
                
            input_iu = self.input_iu_buffer.get()
            iu_memory.append(input_iu)
            
            # IUがREVOKEだった場合はメモリから削除
            if input_iu['update_type'] == RemdisUpdateType.REVOKE:
                iu_memory = self.util_func.remove_revoked_ius(iu_memory)
            # ADD/COMMITの場合は応答候補生成
            else:
                user_utterance = self.util_func.concat_ius_body(iu_memory)
                if user_utterance == '':
                    continue

                # 閾値以上のIUが溜まっているか確認し，溜まっていなければ次のIUもしくはCOMMITを待つ
                if input_iu['update_type'] == RemdisUpdateType.ADD:
                    new_iu_count += 1
                    if new_iu_count < self.text_vap_interval:
                        continue
                    else:
                        new_iu_count = 0

                # パラレルなテキストVAP処理
                t = threading.Thread(
                    target=self.run_text_vap,
                    args=(input_iu['timestamp'],
                          user_utterance)
                )
                t.start()

                # ユーザ発話終端の処理
                if input_iu['update_type'] == RemdisUpdateType.COMMIT:
                    self.is_listening = False
                    self.sent_backchannel_counter = 0
                    iu_memory = []
    
    # テキストVAPの判定結果をパース
    def parse_line_for_text_vap(self, line):
        text_vap_completion = line.strip().split(':')[-1]
        text_vap_score = int(text_vap_completion) if text_vap_completion.isdigit() else 0
        return text_vap_score >= self.min_text_vap_threshold

    # バックチャネルの判定結果をパース
    def parse_line_for_backchannel(self, line):
        backchannel_completion = line.strip().split(':')[-1]
        backchannel_completion = backchannel_completion.split('_')
        if len(backchannel_completion) != 2:
            return 0, ''
        label, content = backchannel_completion
        label = int(label) if label.isdigit() else 0
        return label, content
    
    # 感情の判定結果をパース
    def parse_line_for_expression(self, line):
        return self.parse_line_for_backchannel(line)[0]
    
    # 動きの判定結果をパース
    def parse_line_for_action(self, message):
        return self.parse_line_for_backchannel(message)[0]

    # テキストVAPを実行
    def run_text_vap(self, asr_timestamp, query):
        # ChatGPTに入力するプロンプト
        messages = [
            {'role': 'user', 'content': self.prompts['BC']},
            {'role': 'system', 'content': "OK"},
            {'role': 'user', 'content': query}
        ]
        
        # ChatGPTにプロンプトを入力してストリーミング形式で応答の生成を開始
        self.response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            stream=True
        )

        # ChatGPTの応答を保持しおく変数
        current_completion_line = ""
        nonverbal_backchannel = {}

        # ChatGPTの応答を順次パース
        for chunk in self.response:
            chunk_message = chunk['choices'][0]['delta']
            if 'content' in chunk_message.keys():
                new_token = chunk_message.get('content')

                if not new_token:
                    continue

                current_completion_line += new_token
                current_completion_line = current_completion_line.strip()

                if new_token != '\n':
                    continue

                # 相槌を打つかどうかの判定
                if current_completion_line.startswith('a'):
                    label, content = self.parse_line_for_backchannel(current_completion_line)
                    if label:
                        self.log(f"***** BACKCHANNEL: {query=} {content=} *****")
                        self.send_backchannel(asr_timestamp, {'bc': content})

                # 表出すべき感情の判定
                elif current_completion_line.startswith('b'):
                    label = self.parse_line_for_expression(current_completion_line)
                    if label:
                        nonverbal_backchannel['expression'] = MMDAgentEXLabel.id2expression[label]

                # 表出すべき動きの判定
                elif current_completion_line.startswith('c'):
                    label = self.parse_line_for_action(current_completion_line)
                    if label:  
                        nonverbal_backchannel['action'] = MMDAgentEXLabel.id2action[label]
                    if nonverbal_backchannel:
                        self.log(f"***** BACKCHANNEL: {query=} {nonverbal_backchannel=} *****")
                        self.send_backchannel(asr_timestamp, nonverbal_backchannel)

                # 応答を確定させるかどうかの判定
                elif current_completion_line.startswith('d'):
                    triggered = self.parse_line_for_text_vap(current_completion_line)
                    if triggered:
                        self.log(f"***** TEXT_VAP: {query=} {current_completion_line=} *****")
                        self.send_system_take_turn()

                current_completion_line = ""

    # バックチャネルを送信
    def send_backchannel(self, asr_timestamp, content):
        with self.backchannel_sent_lock:
            triggered = False

            if 'bc' in content:
                if (self.last_verbal_backchannel_timestamp < asr_timestamp
                    and self.is_listening
                    and self.sent_verbal_backchannel_counter < self.max_verbal_backchannel_num):
                    self.last_verbal_backchannel_timestamp = asr_timestamp
                    self.sent_verbal_backchannel_counter += 1
                    triggered = True
                    exchange = 'bc'
            elif 'expression' in content or 'action' in content:
                if (self.last_nonverbal_backchannel_timestamp < asr_timestamp
                    and self.is_listening
                    and self.sent_nonverbal_backchannel_counter < self.max_nonverbal_backchannel_num):
                    self.last_nonverbal_backchannel_timestamp = asr_timestamp
                    self.sent_nonverbal_backchannel_counter += 1
                    triggered = True
                    exchange = 'emo_act'

            if triggered:
                snd_iu = self.createIU(content, exchange, RemdisUpdateType.ADD)
                self.printIU(snd_iu)
                self.publish(snd_iu, exchange)
    
    # システム発話の開始を送信
    def send_system_take_turn(self):
        snd_iu = self.createIU('SYSTEM_TAKE_TURN', 'str', RemdisUpdateType.COMMIT)
        self.printIU(snd_iu)
        self.publish(snd_iu, 'vap')
                            
    # メッセージ受信用コールバック関数
    def callback_asr(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        self.input_iu_buffer.put(in_msg)

    # デバッグ用のログを出力
    def log(self, *args, **kwargs):
        print(f"[{time.time():.5f}]", *args, flush=True, **kwargs)


def main():
    text_vap = TextVAP()
    text_vap.run()


if __name__ == '__main__':
    main()

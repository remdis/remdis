import time
import threading

from base import RemdisModule, RemdisUpdateType

class TOUT(RemdisModule):
    def __init__(self,
                 sub_exchanges=['asr', 'dialogue', 'dialogue2'],
                 pub_exchanges=['tts']):
        super().__init__(pub_exchanges=pub_exchanges,
                         sub_exchanges=sub_exchanges)
        self._is_running = True
    
    def run(self):
        threading.Thread(target=self.listen_asr_loop).start()
        threading.Thread(target=self.listen_dialogue_loop).start()
        threading.Thread(target=self.listen_dialogue2_loop).start()

    def listen_asr_loop(self):
        self.subscribe('asr', self.callback_asr)
    
    def listen_dialogue_loop(self):
        self.subscribe('dialogue', self.callback_dialogue)

    def listen_dialogue2_loop(self):
        self.subscribe('dialogue2', self.callback_dialogue2)

    def callback_asr(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        print('IN(asr):', end='')
        self.printIU(in_msg, flush=True)
    
    def callback_dialogue(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        time.sleep(1)
        print('IN(dialogue):', end='')
        self.printIU(in_msg, flush=True)
        if in_msg['update_type'] == RemdisUpdateType.COMMIT:
            snd_iu = self.createIU('', 'tts', RemdisUpdateType.COMMIT)
            snd_iu['data_type'] = 'audio'
            print('OUT(tts): ', end='')
            self.printIU(snd_iu, flush=True)
            self.publish(snd_iu, 'tts')

    def callback_dialogue2(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)
        print('IN(dialogue2):', end='')
        self.printIU(in_msg, flush=True)

if __name__ == '__main__':
    TOUT().run()
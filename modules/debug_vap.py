import sys, os

from pynput import keyboard

import time
import threading

from base import RemdisModule, RemdisUpdateType

label_conv = {'a': 'BOTH_SILENCE',
              'b': 'SYSTEM_BACKCHANNEL',
              'c': 'SYSTEM_TAKE_TURN',
              'd': 'USER_BACKCHANNEL',
              'e': 'BOTH_BACKCHANNEL',
              'f': 'USER_BACKCHANNEL',
              'g': 'USER_TAKE_TURN',
              'h': 'SYSTEM_BACKCHANNEL',
              'i': 'BOTH_TAKE_TURN'}

class M_VAP(RemdisModule):
    def __init__(self, 
                 pub_exchanges=['vap']):
        super().__init__(pub_exchanges=pub_exchanges)        
        self._is_running = True

    def run(self):
        #t2 = threading.Thread(target=self.send_loop)
        #t2.start()
       with keyboard.Listener(
               on_press=self.on_press) as listener:
           listener.join() 

    def on_press(self, key):
        try:
            if key.char in label_conv.keys():
                message_body = label_conv[key.char]
                snd_iu = self.createIU(message_body,
                                       'str',
                                       RemdisUpdateType.COMMIT)
                self.printIU(snd_iu)
                self.publish(snd_iu, 'vap')
        except AttributeError:
            print('{0} is not defined.'.format(
                key))
        
    """
    def callback(self, ch, method, properties, in_msg):
        in_msg = self.parse_msg(in_msg)

        if in_msg['update_type'] == RemdisUpdateType.REVOKE:
            self.revoked_iu_id_buffer.append(in_msg['id'])
        else:
            self.input_iu_buffer.put(in_msg)
    """

def main():
    m_vap = M_VAP()
    m_vap.run()

if __name__ == '__main__':
    main()

from base import RemdisModule, RemdisUpdateType

class TIN(RemdisModule):
    def __init__(self, pub_exchanges=['asr']):
        super().__init__(pub_exchanges=pub_exchanges)
        self._is_running = True

    def run(self):
        while True:
            asr_token = input('Type phrase and press Enter for ADD, or just press Enter for COMMIT: ').strip()

            if asr_token:
                snd_iu = self.createIU(asr_token, 'asr', RemdisUpdateType.ADD)
            else:
                snd_iu = self.createIU('', 'asr', RemdisUpdateType.COMMIT)

            self.printIU(snd_iu)
            self.publish(snd_iu, 'asr')

if __name__ == '__main__':
    TIN().run()

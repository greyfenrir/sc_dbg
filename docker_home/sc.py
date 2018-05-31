import time
import threading
from multiprocessing import Process
from easyprocess import EasyProcess

class Second(object):
    def __init__(self):
        self.process = None

    def startup(self):        
        thread = threading.Thread(target=self._second)
        thread.start()
        
    def _second(self):
        time.sleep(0.1)
        
        self.process = Process(target=self._sub)
        self.process.start()

    def _sub(self):
        while True:
            pass

    def shutdown(self):
        self.process.terminate()


def main():
        obj = Second()
        obj.startup()
        time.sleep(0.1)

        with EasyProcess('sleep 100'):
            for n in range(0, 2):                
                time.sleep(0.3)

        obj.shutdown()

if __name__ == "__main__":
	main()

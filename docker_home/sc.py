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
        self.process = Process(target=self._sub)
        self.process.start()

    def _sub(self):
        while True:
            time.sleep(1)

    def shutdown(self):
        self.process.terminate()


def main():
    obj = Second()
    obj.startup()

    with EasyProcess('sleep 100'):
        pass


    obj.shutdown()

if __name__ == "__main__":
	main()

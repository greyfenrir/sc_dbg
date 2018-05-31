import time
import threading
from unittest import TestCase
from multiprocessing import Process
from easyprocess import EasyProcess

from bzt.engine import Service


class Second(object):

    def startup(self):        
        thread = threading.Thread(target=self._second)
        thread.start()

    def check(self):
        pass
        
    def _second(self):
        time.sleep(0.1)
        
        self.process = Process(target=self._sub)
        self.process.start()

    def _sub(self):
        while True:
            pass

    def shutdown(self):
        self.process.terminate()


class TestSc(TestCase):
    def t_me(self):
        obj = Second()
        obj.startup()
        time.sleep(0.1)   # preparing of screenshoter subprocess

        with EasyProcess('sleep 100'):
            for n in range(0, 2):
                obj.check()
                time.sleep(0.3)

        obj.shutdown()

if __name__ == "__main__":
	TestSc().t_me()

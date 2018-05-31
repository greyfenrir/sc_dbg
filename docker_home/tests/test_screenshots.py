import os
import time
import logging
import tempfile

from easyprocess import EasyProcess

from bzt.modules.provisioning import Local
from bzt.modules.selenium import SeleniumExecutor
from bzt.modules.services import VirtualDisplay
from unittest import TestCase

from bzt.engine import ScenarioExecutor, Configuration, Engine

import threading
from multiprocessing import Process

from bzt.engine import Service


class Second(Service):

    def startup(self):        
        thread = threading.Thread(target=self._second)
        thread.daemon = True
        thread.start()

    def _second(self):
        time.sleep(0.1)
        
        self.process = Process(target=self._sub)
        self.process.start()

    def sub(self):
        while True:
            pass

    def shutdown(self):
        self.process.terminate()


class EngineEmul(Engine):
    """
    emulating engine
    """

    def __init__(self):
        super(EngineEmul, self).__init__(logging.getLogger(''))
        #self.config.merge({"provisioning": "local"})
        art_dir_pattern = os.path.dirname(__file__) + "/../build/test/%Y-%m-%d_%H-%M-%S.%f"
        self.config.get('settings', force_set=True)['artifacts-dir'] = art_dir_pattern
        self.create_artifacts_dir()        

class TestSecond(TestCase):
    def test_simple(self):
        obj = Second()
        obj.engine = EngineEmul()
        obj.engine.provisioning = Local()
        executor = SeleniumExecutor()
        display = VirtualDisplay()
        display.engine = obj.engine
        obj.engine.services.append(display)
        obj.engine.provisioning.executors.append(executor)

        #obj.prepare()
        display.startup()
        obj.startup()
        time.sleep(0.1)   # preparing of screenshoter subprocess

        with EasyProcess('xmessage hello', env=obj.engine.shared_env.get()):
            for n in range(0, 2):
                obj.check()
                time.sleep(0.2)        

        obj.shutdown()
        display.shutdown()        

        #obj.post_process()
        display.post_process()

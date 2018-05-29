import os
import time

from easyprocess import EasyProcess

from bzt.modules.provisioning import Local
from bzt.modules.selenium import SeleniumExecutor
from bzt.modules.services import VirtualDisplay
from bztcustom.screenshoter import ScreenShoter
from unittest import TestCase as BZTestCase
from tests.mock import EngineEmul


class TestScreenshoter(BZTestCase):
    def test_simple(self):
        obj = ScreenShoter()
        obj.engine = EngineEmul()
        obj.engine.provisioning = Local()
        executor = SeleniumExecutor()
        display = VirtualDisplay()
        display.engine = obj.engine
        obj.engine.services.append(display)
        obj.engine.provisioning.executors.append(executor)

        obj.prepare()
        display.startup()
        obj.startup()
        self.assertEqual(display.get_virtual_display(), obj.virtual_display)
        # time.sleep(1)   # preparing of screenshoter subprocess

        with EasyProcess('xmessage hello', env=obj.engine.shared_env.get()):
            for n in range(0, 2):
                obj.check()
                time.sleep(1)
        with EasyProcess('xmessage bye', env=obj.engine.shared_env.get()):
            for n in range(0, 2):
                obj.check()
                time.sleep(1)

        obj.shutdown()
        display.shutdown()

        scr_dir = os.path.join(obj.engine.artifacts_dir, "scr")
        draft_count = len(os.listdir(scr_dir))          # draft files in dir
        self.assertGreater(draft_count, 2)

        uniq_count = len(obj.uniq_files()["files"])     # uniq files according to screenshoter
        self.assertLess(uniq_count, draft_count)        # part of them should be deleted..

        self.assertEqual(len(os.listdir(scr_dir)), uniq_count)       # unique files in dir

        obj.post_process()
        display.post_process()

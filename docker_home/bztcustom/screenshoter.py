import os
import hashlib
import threading
import time
from collections import OrderedDict
from multiprocessing import Process

import pyscreenshot
from pyvirtualdisplay.smartdisplay import SmartDisplay

from bzt.engine import Service
from bzt.modules.services import VirtualDisplay


class ScreenShoter(Service):
    """
    :type virtual_display: pyvirtualdisplay.smartdisplay.SmartDisplay
    """

    def __init__(self):
        super(ScreenShoter, self).__init__()
        self.interrupted = False
        self.virtual_display = None
        self.size = None
        self.process = None
        self.start_time = None
        self.file = '/tmp/out.txt'
        if os.path.exists(self.file):
            os.remove(self.file)

    def startup(self):
        super(ScreenShoter, self).startup()
        for service in self.engine.services:
            if isinstance(service, VirtualDisplay):
                if self.virtual_display:  # already found
                    self.log.warning('Only one virtual display is supported but found: %s', service)
                    continue

                display = service.get_virtual_display()
                if isinstance(display, SmartDisplay):
                    os.mkdir(self.engine.create_artifact("scr", ""))
                    self.size = display.size
                    self.virtual_display = display
                    self.log.debug("Found display for screenshots: %s", self.virtual_display)

        thread = threading.Thread(target=self.screenshots)
        thread.daemon = True
        thread.start()

    def screenshots(self):
        if not self.virtual_display:
            self.log.warning("Screenshoter requires configured virtual display")
            return

        # while not self.interrupted and not self.engine.interrupted:
        while not (self.virtual_display.is_started and self.virtual_display.is_alive()):
            time.sleep(0.1)

        # avoid temporary unavailability of virtual display. Is there some specific 'is_alive' for that?
        time.sleep(1)

        self.start_time = time.time()

        w, h = self.size
        box = [self.settings.get("crop-left", 0),
               self.settings.get("crop-top", 0),
               w - self.settings.get("crop-right", 0),
               h - self.settings.get("crop-bottom", 0)]

        # cropped size
        self.size = (box[2] - box[0], box[3] - box[1])

        # run grabber in subprocess (with its own environment)
        self.process = Process(target=self._grab, args=(box,))
        self.process.daemon = True
        self.process.start()

    def _grab(self, box):
        """ grabber subprocess """
        # point subprocess to virtual display
        if self.engine.shared_env.get("DISPLAY"):
            os.environ["DISPLAY"] = self.engine.shared_env.get("DISPLAY")

        backend = self.virtual_display.pyscreenshot_backend
        loader = pyscreenshot.loader.Loader()
        loader.force(backend)
        backend_obj = loader.selected()

        # grab as quickly as possible. should we add timeout there?
        while True:
            try:
                with open(self.file, 'a') as _f: _f.write('before grab()\n')
                img = backend_obj.grab(None)
                with open(self.file, 'a') as _f: _f.write('after grab()\n\n')
                if img:
                    tstmp = int(time.time() * 1000)
                    img_file = self.engine.create_artifact("scr/%s" % tstmp, ".jpg")
                    if sum(box):
                        img = img.crop(box)
                    img.save(img_file)

            except KeyboardInterrupt:
                with open(self.file, 'a') as _f:
                    _f.write('exc KBD\n\n')
                raise

            except BaseException:
                with open(self.file, 'a') as _f:
                    _f.write('exc BaseExc\n\n')
                time.sleep(1)

    def shutdown(self):
        with open(self.file, 'a') as _f:
            _f.write('shutdown()\n\n')
        super(ScreenShoter, self).shutdown()
        with open(self.file, 'a') as _f:
            _f.write('shutdown: try to termitate proc\n\n')
        self.process.terminate()
        with open(self.file, 'a') as _f:
            _f.write('shutdown: proc terminated\n\n')

        self.interrupted = True

    def uniq_files(self):
        cur_hash = None
        cfiles = os.listdir(os.path.join(self.engine.artifacts_dir, "scr"))

        speed = len(cfiles) / (time.time() - self.start_time)
        self.log.info("Screenshoter speed: %.1f fps", speed)
        files = OrderedDict()

        for cfile in cfiles:
            tstmp = int(cfile[:-4])
            files[tstmp] = os.path.join("scr", cfile)

        cfiles = sorted(list(files.keys()))

        for tstmp in cfiles:
            name = files[tstmp]
            fname = os.path.join(self.engine.artifacts_dir, name)

            if not os.path.getsize(fname):
                self.log.debug("Empty file, removing: %s", fname)
                os.remove(fname)
                del files[tstmp]
                continue

            md5 = hashlib.md5()
            with open(fname, "rb") as fdh:
                md5.update(fdh.read())
                hsh = md5.hexdigest()
                if hsh == cur_hash:
                    self.log.debug("Hash match %s, removing: %s", hsh, fname)
                    os.remove(fname)
                    del files[tstmp]
                cur_hash = hsh

        return {"size": self.size, "files": files}

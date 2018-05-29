import sys
_mswindows = (sys.platform == "win32")

import errno
import builtins
import io
import os
import time
import warnings
import threading

import _posixsubprocess
import subprocess
import tempfile
from easyprocess.unicodeutil import uniencode
from easyprocess import EasyProcess, EasyProcessError

from bzt.modules.provisioning import Local
from bzt.modules.selenium import SeleniumExecutor
from bzt.modules.services import VirtualDisplay
from bztcustom.screenshoter import ScreenShoter
from unittest import TestCase as BZTestCase
from tests.mock import EngineEmul
import logging
from fcntl import fcntl, F_GETFL
from os import O_NONBLOCK


log = logging.getLogger(__name__)
class SubprocessError(Exception): pass
_PLATFORM_DEFAULT_CLOSE_FDS = object()

_active = []

def _cleanup():
    for inst in _active[:]:
        res = inst._internal_poll(_deadstate=sys.maxsize)
        if res is not None:
            try:
                _active.remove(inst)
            except ValueError:
                # This can happen if two threads create a new Popen instance.
                # It's harmless that it was already removed, so ignore.
                pass

PIPE = -1
STDOUT = -2
DEVNULL = -3


class MockPopen(subprocess.Popen):
    _child_created = False  # Set here since __del__ checks it

    def __init__(self, args, bufsize=-1, executable=None,
                 stdin=None, stdout=None, stderr=None,
                 preexec_fn=None, close_fds=_PLATFORM_DEFAULT_CLOSE_FDS,
                 shell=False, cwd=None, env=None, universal_newlines=False,
                 startupinfo=None, creationflags=0,
                 restore_signals=True, start_new_session=False,
                 pass_fds=(), dfile=None):
        """Create new Popen instance."""
        _cleanup()
        # Held while anything is calling waitpid before returncode has been
        # updated to prevent clobbering returncode if wait() or poll() are
        # called from multiple threads at once.  After acquiring the lock,
        # code must re-check self.returncode to see if another thread just
        # finished a waitpid() call.
        self.dfile = dfile
        self._waitpid_lock = threading.Lock()

        self._input = None
        self._communication_started = False
        if bufsize is None:
            bufsize = -1  # Restore default
        if not isinstance(bufsize, int):
            raise TypeError("bufsize must be an integer")

        if _mswindows:
            if preexec_fn is not None:
                raise ValueError("preexec_fn is not supported on Windows "
                                 "platforms")
            any_stdio_set = (stdin is not None or stdout is not None or
                             stderr is not None)
            if close_fds is _PLATFORM_DEFAULT_CLOSE_FDS:
                if any_stdio_set:
                    close_fds = False
                else:
                    close_fds = True
            elif close_fds and any_stdio_set:
                raise ValueError(
                        "close_fds is not supported on Windows platforms"
                        " if you redirect stdin/stdout/stderr")
        else:
            # POSIX
            if close_fds is _PLATFORM_DEFAULT_CLOSE_FDS:
                close_fds = True
            if pass_fds and not close_fds:
                warnings.warn("pass_fds overriding close_fds.", RuntimeWarning)
                close_fds = True
            if startupinfo is not None:
                raise ValueError("startupinfo is only supported on Windows "
                                 "platforms")
            if creationflags != 0:
                raise ValueError("creationflags is only supported on Windows "
                                 "platforms")

        self.args = args
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.pid = None
        self.returncode = None
        self.universal_newlines = universal_newlines

        (p2cread, p2cwrite,
         c2pread, c2pwrite,
         errread, errwrite) = self._get_handles(stdin, stdout, stderr)

        if p2cwrite != -1:
            self.stdin = io.open(p2cwrite, 'wb', bufsize)
            if universal_newlines:
                self.stdin = io.TextIOWrapper(self.stdin, write_through=True,
                                              line_buffering=(bufsize == 1))
        if c2pread != -1:
            self.stdout = io.open(c2pread, 'rb', bufsize)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)
        if errread != -1:
            self.stderr = io.open(errread, 'rb', bufsize)
            if universal_newlines:
                self.stderr = io.TextIOWrapper(self.stderr)

        self._closed_child_pipe_fds = False
        try:
            with open(dfile, 'a') as tf:
                tf.write('before execute_child()\n')
            self._execute_child(args, executable, preexec_fn, close_fds,
                                pass_fds, cwd, env,
                                startupinfo, creationflags, shell,
                                p2cread, p2cwrite,
                                c2pread, c2pwrite,
                                errread, errwrite,
                                restore_signals, start_new_session)
        except:
            # Cleanup if the child failed starting.
            with open(dfile, 'a') as tf:
                tf.write('exception in execute_child()\n')

            for f in filter(None, (self.stdin, self.stdout, self.stderr)):
                try:
                    f.close()
                except OSError:
                    pass  # Ignore EBADF or other errors.


            if not self._closed_child_pipe_fds:
                to_close = []
                if stdin == PIPE:
                    to_close.append(p2cread)
                if stdout == PIPE:
                    to_close.append(c2pwrite)
                if stderr == PIPE:
                    to_close.append(errwrite)
                if hasattr(self, '_devnull'):
                    to_close.append(self._devnull)
                for fd in to_close:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

            raise
        with open(dfile, 'a') as tf:
            tf.write('after execute_child\n')

    def _execute_child(self, args, executable, preexec_fn, close_fds,
                       pass_fds, cwd, env,
                       startupinfo, creationflags, shell,
                       p2cread, p2cwrite,
                       c2pread, c2pwrite,
                       errread, errwrite,
                       restore_signals, start_new_session):
        """Execute program (POSIX version)"""

        if isinstance(args, (str, bytes)):
            args = [args]
        else:
            args = list(args)

        if shell:
            args = ["/bin/sh", "-c"] + args
            if executable:
                args[0] = executable

        if executable is None:
            executable = args[0]
        orig_executable = executable

        # For transferring possible exec failure from child to parent.
        # Data format: "exception name:hex errno:description"
        # Pickle is not used; it is complex and involves memory allocation.
        errpipe_read, errpipe_write = os.pipe()
        # errpipe_write must not be in the standard io 0, 1, or 2 fd range.
        low_fds_to_close = []
        while errpipe_write < 3:
            low_fds_to_close.append(errpipe_write)
            errpipe_write = os.dup(errpipe_write)
        for low_fd in low_fds_to_close:
            os.close(low_fd)
        try:
            try:
                # We must avoid complex work that could involve
                # malloc or free in the child process to avoid
                # potential deadlocks, thus we do all this here.
                # and pass it to fork_exec()

                if env is not None:
                    env_list = []
                    for k, v in env.items():
                        k = os.fsencode(k)
                        if b'=' in k:
                            raise ValueError("illegal environment variable name")
                        env_list.append(k + b'=' + os.fsencode(v))
                else:
                    env_list = None  # Use execv instead of execve.
                executable = os.fsencode(executable)
                if os.path.dirname(executable):
                    executable_list = (executable,)
                else:
                    # This matches the behavior of os._execvpe().
                    executable_list = tuple(
                        os.path.join(os.fsencode(dir), executable)
                        for dir in os.get_exec_path(env))
                fds_to_keep = set(pass_fds)
                fds_to_keep.add(errpipe_write)
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): before fork(args=%s, executable_list=%s, preexec_fn=%s)\n'
                             % (args, executable_list, preexec_fn))
                    tf.write('errpipe_write %sin fds_to_keep\n' % ('' if errpipe_write in fds_to_keep else 'not '))
                self.pid = _posixsubprocess.fork_exec(
                    args, executable_list,
                    close_fds, tuple(sorted(map(int, fds_to_keep))),
                    cwd, env_list,
                    p2cread, p2cwrite, c2pread, c2pwrite,
                    errread, errwrite,
                    errpipe_read, errpipe_write,
                    restore_signals, start_new_session, preexec_fn)
                self._child_created = True
            finally:
                # be sure the FD is closed no matter what
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): after fork() %s\n' % str(os.fstat(errpipe_write)))
                    tf.write("errpipe_write.O_NONBLOCK: %s\n" % (fcntl(errpipe_read, F_GETFL) & O_NONBLOCK))
                os.close(errpipe_write)
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): after closing errpipe_write %s\n' % str(os.fstat(errpipe_write)))

            # self._devnull is not always defined.
            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): 1\n')
            devnull_fd = getattr(self, '_devnull', None)
            if p2cread != -1 and p2cwrite != -1 and p2cread != devnull_fd:
                os.close(p2cread)
            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): 2\n')
            if c2pwrite != -1 and c2pread != -1 and c2pwrite != devnull_fd:
                os.close(c2pwrite)
            if errwrite != -1 and errread != -1 and errwrite != devnull_fd:
                os.close(errwrite)
            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): 3\n')
            if devnull_fd is not None:
                os.close(devnull_fd)
            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): 4\n')
            # Prevent a double close of these fds from __init__ on error.
            self._closed_child_pipe_fds = True

            # Wait for exec to fail or succeed; possibly raising an
            # exception (limited in size)
            errpipe_data = bytearray()
            with open(self.dfile, 'a') as tf:
                tf.write('pid: %s\n' % self.pid)
                tf.write('execute_child(): 5 (while True) errpipe_read: %s\n' % str(os.fstat(errpipe_read)))
                tf.write("errpipe_read.O_NONBLOCK: %s\n" % (fcntl(errpipe_read, F_GETFL) & O_NONBLOCK))
            while True:
                part = os.read(errpipe_read, 50000)
                errpipe_data += part
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): part: %s, errpipe_data: %s\n' % (len(part), len(errpipe_data)))
                if not part or len(errpipe_data) > 50000:
                    break

            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): 6\n')
        finally:
            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): after external try\n')
            # be sure the FD is closed no matter what
            os.close(errpipe_read)

        if errpipe_data:
            try:
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): os.waitpid\n')
                os.waitpid(self.pid, 0)
            except ChildProcessError as exc:
                with open(self.dfile, 'a') as tf:
                    tf.write('execute_child(): child error: %s\n' % exc)
                pass

            with open(self.dfile, 'a') as tf:
                tf.write('execute_child(): before the last try\n')
            try:
                exception_name, hex_errno, err_msg = (
                    errpipe_data.split(b':', 2))
            except ValueError:
                exception_name = b'SubprocessError'
                hex_errno = b'0'
                err_msg = (b'Bad exception data from child: ' +
                           repr(errpipe_data))
            child_exception_type = getattr(
                builtins, exception_name.decode('ascii'),
                SubprocessError)
            err_msg = err_msg.decode(errors="surrogatepass")
            if issubclass(child_exception_type, OSError) and hex_errno:
                errno_num = int(hex_errno, 16)
                child_exec_never_called = (err_msg == "noexec")
                if child_exec_never_called:
                    err_msg = ""
                if errno_num != 0:
                    err_msg = os.strerror(errno_num)
                    if errno_num == errno.ENOENT:
                        if child_exec_never_called:
                            # The error must be from chdir(cwd).
                            err_msg += ': ' + repr(cwd)
                        else:
                            err_msg += ': ' + repr(orig_executable)
                raise child_exception_type(errno_num, err_msg)
            raise child_exception_type(err_msg)


class MockEasyProcess(EasyProcess):
    def start(self):
        """start command in background and does not wait for it.

        :rtype: self

        """
        efile = '/tmp/out_e.txt'
        if os.path.exists(efile):
            os.remove(efile)
        if self.is_started:
            raise EasyProcessError(self, 'process was started twice!')

        if self.use_temp_files:
            self._stdout_file = tempfile.TemporaryFile(prefix='stdout_')
            self._stderr_file = tempfile.TemporaryFile(prefix='stderr_')
            stdout = self._stdout_file
            stderr = self._stderr_file

        else:
            stdout = subprocess.PIPE
            stderr = subprocess.PIPE

        cmd = list(map(uniencode, self.cmd))

        try:
            with open(efile, 'a') as tf:
                tf.write('before popen(%s, stdout=%s, stderr=%s, cwd=%s, env=%s\n' %
                         (cmd, stdout, stderr, self.cwd, self.env))
            self.popen = MockPopen(cmd, stdout=stdout, stderr=stderr, cwd=self.cwd, env=self.env, dfile=efile)

        except OSError as oserror:
            with open(efile, 'a') as tf:
                tf.write('popen: raises OSError: %s\n' % oserror)

            log.debug('OSError exception: %s', oserror)
            self.oserror = oserror
            raise EasyProcessError(self, 'start error')
        except BaseException as exc:
            with open(efile, 'a') as tf:
                tf.write('popen: raise %s\n' % exc)
        with open(efile, 'a') as tf:
            tf.write('after popen\n')

        self.is_started = True

        log.debug('process was started (pid=%s)', self.pid)
        return self


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
        time.sleep(1)   # preparing of screenshoter subprocess

        tfile = '/tmp/out_t.txt'
        if os.path.exists(tfile):
            os.remove(tfile)

        with open(tfile, 'a') as tf: tf.write('before hello\n')

        with MockEasyProcess('xmessage hello', env=obj.engine.shared_env.get()):
            for n in range(0, 2):
                with open(tfile, 'a') as tf: tf.write('in hello: %s\n' % n)
                obj.check()
                time.sleep(1)

        with open(tfile, 'a') as tf: tf.write('before bue\n')
        with MockEasyProcess('xmessage bye', env=obj.engine.shared_env.get()):
            for n in range(0, 2):
                with open(tfile, 'a') as tf: tf.write('in bue: %s\n' % n)
                obj.check()
                time.sleep(1)

        obj.shutdown()

        scr_dir = os.path.join(obj.engine.artifacts_dir, "scr")
        draft_count = len(os.listdir(scr_dir))          # draft files in dir
        self.assertGreater(draft_count, 2)

        uniq_count = len(obj.uniq_files()["files"])     # uniq files according to screenshoter
        self.assertLess(uniq_count, draft_count)        # part of them should be deleted..

        self.assertEqual(len(os.listdir(scr_dir)), uniq_count)       # unique files in dir

        obj.post_process()
        display.post_process()

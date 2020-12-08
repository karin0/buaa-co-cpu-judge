import os, sys, multiprocessing, threading, glob
from random import randint
from queue import Queue, Empty

from .base import \
    BaseJudge, VerificationFailed, mars_path_default, tmp_pre, kill_pid, kill_im, diff_path_default, mars_timeout_default, \
    hash_file
from .atomic import Atomic, Counter

tb_timeout_default = 5
pc_start_default = 0x3000
duration_default = '1000 us'

tcl_common_fn = 'judge.cmd'
hex_common_fn = 'code.txt'


class PropagatingThread(threading.Thread):
    def run(self):
        self.exc = None
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e

    def join(self):
        super(PropagatingThread, self).join()
        if self.exc:
            raise self.exc
        return self.ret


class ISimJudge(BaseJudge):

    def __init__(self, tb_path, ise_path=None,
                 mars_path=mars_path_default,
                 java_path='java',
                 diff_path=diff_path_default,
                 db=False,
                 np=False,
                 duration=duration_default,
                 pc_start=pc_start_default
                 ):
        super().__init__()

        self.tb_path = tb_path
        self.pc_start = pc_start
        self.db = db
        self.np = np

        self.mars_path = mars_path
        self.java_path = java_path
        self.diff_path = diff_path

        self.tb_basename = os.path.basename(tb_path)
        self.tb_dir = tb_dir = os.path.dirname(tb_path)
        self.tcl_common_path = os.path.join(tb_dir, tcl_common_fn)
        self.tcl_common_text = 'run {}\nexit\n'.format(duration)
        self._generate_tcl(self.tcl_common_path, self.tcl_common_text)
        self.hex_common_path = os.path.join(tb_dir, hex_common_fn)

        self.env = env = os.environ.copy()
        if ise_path is not None:
            ise = ise_path if os.path.isdir(os.path.join(ise_path, 'bin')) else os.path.join(ise_path, 'ISE')
            bin = os.path.join(ise, 'bin')
            platform = 'nt' if os.name == 'nt' else 'lin'
            if os.path.isdir(os.path.join(bin, platform + '64')):
                platform += '64'
            platform_bin = os.path.join(bin, platform)

            env['XILINX'] = ise
            env['XILINX_PLATFORM'] = platform
            env['PATH'] = platform_bin + os.pathsep + env['PATH']

    @staticmethod
    def _generate_tcl(path, s):
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(s)

    @staticmethod
    def _parse(s):
        if 'error' in s.lower():
            raise VerificationFailed('ISim complained ' + s)
        if '$ 0' in s:
            return
        p = s.find('@')
        if p >= 0:
            return s[p:]

    def __call__(self, asm_path,
                 tb_timeout=tb_timeout_default,
                 mars_timeout=mars_timeout_default,
                 keep_output_files=False,
                 _tcl_fn=tcl_common_fn,
                 _hex_path=None,
                 _used_identifiers=None
                 ):
        if _hex_path is None:
            _hex_path = self.hex_common_path

        identifier = os.path.basename(asm_path)

        if _used_identifiers is not None:
            with _used_identifiers as s:
                if identifier in s:
                    print('Renaming duplicated output filename for', asm_path, file=sys.stderr)
                    identifier += '-' + hash_file(asm_path)
                    if identifier in s:
                        print('Renaming duplicated output filename for', asm_path,
                              file=sys.stderr)
                        identifier += '-' + str(randint(10000, 99999))
                        if identifier in s:
                            raise VerificationFailed('Unresolvable naming conflicts for ' + asm_path)
                s.add(identifier)

        ans_path = os.path.join(tmp_pre, identifier + '.ans')
        self.call_mars(asm_path, _hex_path, ans_path,
                       timeout=mars_timeout)

        out_path = os.path.join(tmp_pre, identifier + '.out')
        print('Running simulation for', asm_path, '...', flush=True)
        self._communicate([self.tb_path, '-tclbatch', _tcl_fn],
                          out_path, self._parse, tb_timeout,
                          'see ' + out_path, 'ISim',
                          error_msg='maybe ISE path is incorrect',
                          cwd=self.tb_dir, env=self.env, nt_kill=True
                          )
        self.diff(out_path, ans_path,
                  log_path=os.path.join(tmp_pre, identifier + '.diff'),
                  keep=keep_output_files)

    def all(self, asm_paths, fn_wire,
            tb_timeout=tb_timeout_default,
            mars_timeout=mars_timeout_default,
            keep_output_files=False,
            workers_num=None,
            recursive=True,
            use_glob=True,
            blocklist=None,
            on_success=None,
            on_error=None,
            on_omit=None,
            kill_on_error=False,
            stop_on_error=True
            ):
        if workers_num is None:
            workers_num = max(multiprocessing.cpu_count() - 2, 2)

        if isinstance(asm_paths, str):
            paths = [asm_paths]
        elif use_glob:
            paths = sum((glob.glob(path, recursive=recursive) for path in asm_paths), start=[])
        else:
            paths = asm_paths

        q = Queue()
        if blocklist:
            ban_set = set(os.path.abspath(path) for path in blocklist)
            def push(path):
                if path in ban_set:
                    if on_omit:
                        on_omit(path)
                else:
                    q.put_nowait(path)
        else:
            push = q.put_nowait

        for path in paths:
            if recursive and os.path.isdir(path):
                for asm_path in glob.glob(os.path.join(path, '**', '*.asm'), recursive=True):
                    push(asm_path)
            else:
                push(path)
        workers = []
        identifiers = Atomic(set())

        total = q.qsize()
        cnt = Counter()
        stop_cnt = Counter()

        def kill():
            print('Killing current process', file=sys.stderr)
            kill_pid(os.getpid())
            kill_im(self.tb_basename)

        def stop():
            with stop_cnt as scnt:
                if not scnt:
                    print('Stopping', file=sys.stderr)
                    stop_cnt.increase()
            kill_im(self.tb_basename)

        def worker(n):
            hex_fn = 'case{:04d}'.format(n)
            tcl_fn = hex_fn + '.cmd'
            hex_path = os.path.join(self.tb_dir, hex_fn)
            tcl_path = os.path.join(self.tb_dir, tcl_fn)

            force = 'isim force add {} {} -radix hex\ninit\n'.format(fn_wire, bytes(hex_fn, encoding='utf-8').hex())
            tcl = force + self.tcl_common_text
            self._generate_tcl(tcl_path, tcl)

            asm_path = None
            retrying = False
            while True:
                if stop_cnt.data:
                    return
                if not retrying:
                    try:
                        asm_path = q.get_nowait()
                    except Empty:
                        return

                retrying = False
                try:
                    self(asm_path,
                         tb_timeout=tb_timeout,
                         mars_timeout=mars_timeout,
                         keep_output_files=keep_output_files,
                         _tcl_fn=tcl_fn,
                         _hex_path=hex_path,
                         _used_identifiers=identifiers
                         )
                except BaseException as e:
                    if isinstance(e, VerificationFailed):
                        se = str(e)
                        if 'tmp_save' in se and 'for write' in se:  # this happens on isim occasionally
                            retrying = True
                            print('Retrying', asm_path, 'as', se)
                            continue

                    # __import__('traceback').print_exc()
                    print('!!', asm_path + ':', e, file=sys.stderr)
                    if on_error:
                        on_error(asm_path)
                    if kill_on_error:
                        return kill()
                    if stop_on_error:
                        return stop()
                    print('Skipping', asm_path)
                else:
                    cnt.increase()
                    print(f'{cnt}/{total}', asm_path, 'ok')
                    if on_success:
                        on_success(asm_path)

        if workers_num == 1:
            return worker(0)

        for i in range(workers_num):
            t = PropagatingThread(target=worker, args=(i,), daemon=True)
            t.start()
            workers.append(t)

        for t in workers:
            t.join()

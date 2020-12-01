import os, sys, multiprocessing, threading, traceback
from queue import Queue, Empty

from .base import \
    BaseJudge, VerificationFailed, mars_path_default, tmp_pre, diff_path_default, mars_timeout_default, hash_file
from .atomic import Set

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

    def __init__(self, tb_path, ise_path,
                 mars_path=mars_path_default,
                 java_path='java',
                 diff_path=diff_path_default,
                 db=False,
                 duration=duration_default,
                 pc_start=pc_start_default
                 ):
        super().__init__()

        self.tb_path = tb_path
        self.ise_path = ise_path
        self.pc_start = pc_start
        self.db = db

        self.mars_path = mars_path
        self.java_path = java_path
        self.diff_path = diff_path

        self.tb_dir = tb_dir = os.path.dirname(tb_path)
        self.tcl_common_path = os.path.join(tb_dir, tcl_common_fn)
        self.tcl_common_text = 'run {}\nexit\n'.format(duration)
        self._generate_tcl(self.tcl_common_path, self.tcl_common_text)
        self.hex_common_path = os.path.join(tb_dir, hex_common_fn)

        ise = ise_path if os.path.isdir(os.path.join(ise_path, 'bin')) else os.path.join(ise_path, 'ISE')
        bin = os.path.join(ise, 'bin')
        platform, exe = (('lin', ''), ('nt', '.exe'))[os.name == 'nt']
        if os.path.isdir(os.path.join(bin, platform + '64')):
            platform += '64'
        platform_bin = os.path.join(bin, platform)

        self.env = env = dict(os.environ.copy(), XILINX=ise, EXE=exe, XILINX_PLATFORM=platform)
        env['PATH'] = platform_bin + os.pathsep + env['PATH']

    @staticmethod
    def _generate_tcl(path, s):
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(s)

    @staticmethod
    def _parse(s):
        if 'error' in s.lower():
            raise VerificationFailed('ISim reported ' + s)
        p = s.find('@')
        if p >= 0:
            return s[p:]

    def __call__(self, asm_path,
                 tb_timeout=tb_timeout_default,
                 mars_timeout=mars_timeout_default,
                 _tcl_fn=tcl_common_fn,
                 _hex_path=None,
                 _ongoing_identifiers=None
                 ):
        if _hex_path is None:
            _hex_path = self.hex_common_path

        fix = '-' + hash_file(asm_path)
        identifier = None
        if _ongoing_identifiers is not None:
            identifier = os.path.basename(asm_path) + fix
            if identifier in _ongoing_identifiers:
                print(asm_path, 'is duplicated and skipped', file=sys.stderr)
                return
            _ongoing_identifiers.add(identifier)

        ans_path = os.path.join(tmp_pre, os.path.basename(asm_path) + fix + '.ans')
        self.call_mars(asm_path, _hex_path, ans_path,
                       timeout=mars_timeout, db=self.db)

        out_path = os.path.join(tmp_pre, os.path.basename(asm_path) + fix + '.out')
        print('Running tb...', flush=True)
        self._communicate([self.tb_path, '-tclbatch', _tcl_fn],
                          out_path, self._parse, tb_timeout,
                          'see ' + out_path, 'ISim',
                          error_msg='maybe ISE path is incorrect ({})'.format(self.ise_path),
                          cwd=self.tb_dir, env=self.env, nt_kill=True
                          )
        self.diff(out_path, ans_path)
        if identifier:
            _ongoing_identifiers.remove(identifier)

    def all(self, asm_paths, fn_wire,
            tb_timeout=tb_timeout_default,
            mars_timeout=mars_timeout_default,
            workers_num=None,
            on_success=None,
            on_error=None
            ):
        if workers_num is None:
            workers_num = max(multiprocessing.cpu_count() - 1, 2)

        q = Queue()
        for path in asm_paths:
            q.put_nowait(path)

        workers = []
        identifiers = Set()

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
                         _tcl_fn=tcl_fn,
                         _hex_path=hex_path,
                         _ongoing_identifiers=identifiers
                         )
                except BaseException as e:
                    if isinstance(e, VerificationFailed):
                        se = str(e)
                        if 'tmp_save' in se and 'for write' in se:  # this happens to isim occasionally
                            retrying = True
                            print('Retrying', asm_path, 'as', se)
                            continue

                    traceback.print_exc()
                    if on_error and on_error(asm_path):
                        return
                else:
                    if on_success:
                        on_success(asm_path)

        for i in range(workers_num):
            t = PropagatingThread(target=worker, args=(i, ), daemon=True)
            t.start()
            workers.append(t)

        for t in workers:
            t.join()

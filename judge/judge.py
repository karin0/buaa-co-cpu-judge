import os, sys, shutil
from random import randint
from typing import Iterable, Optional

from .base import BaseHexRunner, VerificationFailed
from .mars import Mars, SegmentNotFoundError
from .diff import Diff
from .utils import TmpDir

tmp_pre = 'tmp'

handler_segment = '0x4180-0x4ffc'

def sync_path(src, dst):
    if not is_path_same(dst, src):
        shutil.copy(src, dst)

class BaseJudge:
    def __init__(self, runners: Iterable[BaseHexRunner],
                 mars: Mars, diff: Optional[Diff] = None):
        self.runners = runners
        self.mars = mars
        self.diff = Diff() if diff is None else diff
        self.id = randint(100000, 999999)
        self.tmp_dir = tmp_dir = TmpDir(os.path.join(tmp_pre, str(self.id)))
        for runner in runners:
            runner.set_tmp_dir(tmp_dir)

    def get_path(self, get, set, fn):
        r = get()
        if r is None:
            r = os.path.join(self.tmp_dir(), fn)
            set(r)
        return r

    def get_hex_path(self, runner: BaseHexRunner, asm_base):
        return self.get_path(runner.get_hex_path, runner.set_hex_path,
                             asm_base + '.hex')

    def get_handler_hex_path(self, runner: BaseHexRunner, asm_base):
        return self.get_path(runner.get_handler_hex_path, runner.set_handler_hex_path,
                             asm_base + '-h.hex')

    def dump_handler(self, asm_path, hex_path):
        try:
            self.mars(asm_path=asm_path, hex_path=hex_path, a=True,
                      dump_segment=handler_segment)
        except SegmentNotFoundError as e:
            print('Warning: no handler found in', asm_path, file=sys.stderr)
            return False
        return True

    def load_handler(self, asm_path):
        source = None
        q = []
        for runner in self.runners:
            path = runner.get_handler_hex_path()
            if path is None:
                q.append(runner)
            else:
                if source is None:
                    source = path
                    if not self.dump_handler(asm_path, path):
                        return False
                else:
                    sync_path(source, path)

        if q:
            if not source:
                source = os.path.join(self.tmp_dir(), os.path.basename(asm_path) + '.hex')
                if not self.dump_handler(asm_path, source):
                    return False
            for runner in q:
                runner.set_handler_hex_path(source)

        print('Loaded handler from', asm_path)
        return True

    def stop(self):
        for runner in self.runners:
            runner.stop()

    @staticmethod
    def __call__(asm_path):
        raise TypeError

    def judge_handler(self, asm_path):
        self.load_handler(asm_path)
        self(asm_path)

    def all(self, asm_paths,
            self_handler=None,
            fallback_handler_keyword=None,
            fallback_handler_asm_path=None,
            on_success=None,
            on_error=None,
            stop_on_error=True,
            permit_missing_segment=True,
            reraise=False
            ):
        total = len(asm_paths)
        cnt = 0
        for path in asm_paths:
            try:
                if self_handler and not self.load_handler(path):
                    loaded = False
                    if fallback_handler_asm_path and os.path.exists(fallback_handler_asm_path):
                        fallback = fallback_handler_asm_path
                        print('Fallback to handler', fallback)
                        loaded = self.load_handler(fallback)
                    if not loaded and fallback_handler_keyword:
                        dirname = os.path.dirname(os.path.abspath(path))
                        for fn in os.listdir(dirname):
                            if fn.endswith('.asm') and fallback_handler_keyword in fn:
                                fallback = os.path.join(dirname, fn)
                                print('Fallback to handler', fallback)
                                loaded = self.load_handler(fallback)
                                if loaded:
                                    break
                    if not loaded:
                        print('No valid handlers found, keeping the previous one')
                self(path)
            except VerificationFailed as e:
                print('!!', path + ':', e.__class__.__name__, e, file=sys.stderr)
                if isinstance(e, SegmentNotFoundError) and permit_missing_segment:
                    print('!! Permitted')
                else:
                    if on_error:
                        on_error(path)
                    if reraise:
                        raise e
                    if stop_on_error:
                        return self.stop()
            else:
                cnt += 1
                print('{}/{}'.format(cnt, total), path, 'ok')
                if on_success:
                    on_success(path)


common_tmp = TmpDir(tmp_pre)
def get_paths(asm_path):
    base = os.path.basename(asm_path)
    pre = common_tmp()
    return base, os.path.join(pre, base + '.out'), os.path.join(pre, base + '.ans')


class MarsJudge(BaseJudge):
    def __init__(self, runner: BaseHexRunner, mars: Mars,
                 diff: Optional[Diff] = None):
        super().__init__([runner], mars, diff)
        self.runner = runner

    def __call__(self, asm_path):
        base, out_path, ans_path = get_paths(asm_path)
        hex_path = self.get_hex_path(self.runner, base)

        if self.mars.permit_timeout:
            self.mars(asm_path=asm_path, hex_path=hex_path, a=True)
            self.mars(asm_path=asm_path, out_path=ans_path)
        else:
            self.mars(asm_path=asm_path, out_path=ans_path, hex_path=hex_path)

        print('Running simulation for', asm_path, '...')
        self.runner(out_path)
        self.diff(out_path, ans_path)


def is_path_same(path1, path2):
    return os.path.relpath(path1, path2) == '.'


class DuetJudge(BaseJudge):
    def __init__(self, runner: BaseHexRunner, runner_std: BaseHexRunner, mars: Mars,
                 diff: Optional[Diff] = None):
        super().__init__([runner, runner_std], mars, diff)
        self.runner = runner
        self.runner_std = runner_std

    def __call__(self, asm_path):
        base, out_path, ans_path = get_paths(asm_path)
        hex_path = self.get_hex_path(self.runner, base)
        hex_std_path = self.get_hex_path(self.runner_std, base)

        self.mars(asm_path=asm_path, hex_path=hex_path, a=True)
        sync_path(hex_path, hex_std_path)

        print('Running standard simulation for', asm_path, '...')
        self.runner_std(ans_path)

        print('Running simulation for', asm_path, '...')
        self.runner(out_path)

        self.diff(out_path, ans_path)


class DummyJudge(MarsJudge):
    def __call__(self, asm_path):
        base, out_path, _ = get_paths(asm_path)
        hex_path = self.get_hex_path(self.runner, base)

        self.mars(asm_path=asm_path, hex_path=hex_path, a=True)
        print('Running simulation for', asm_path, '...')
        self.runner(out_path)
        print('Output to', out_path)

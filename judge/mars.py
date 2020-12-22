import os, subprocess
from .base import BaseRunner, VerificationFailed

mars_path_default = os.path.join(os.path.dirname(__file__), 'kits', 'marsx.jar')


class MarsError(VerificationFailed):
    pass


class SegmentNotFoundError(MarsError):
    pass


def render_arg(name, value, fallback=''):
    return name if value else fallback


class Mars(BaseRunner):
    name = 'MARS'

    def __init__(self, mars_path=None, java_path='java', db=False, np=False, a=False, **kw):
        super().__init__(**kw)
        self.mars_path = mars_path_default if mars_path is None else mars_path
        self.java_path = java_path
        self.db = render_arg('db', db)
        self.np = render_arg('np', np)
        self.a = render_arg('a', a)

        if not db:
            print('Delayed branching is disabled')

    def set_assemble_only(self):
        self.a = 'a'

    @staticmethod
    def parse(s):
        sl = s.lower()
        if 'error' in sl:
            raise MarsError('MARS reported ' + s)
        if 'nothing to dump' in sl:
            raise SegmentNotFoundError(sl)
        if '$ 0' in s:
            return
        if s.startswith('@'):
            return s

    def start(self, asm_path):
        subprocess.run([self.java_path, '-jar', self.mars_path, asm_path])

    def __call__(self, asm_path, out_path=None, hex_path=None, a=False, dump_segment='.text'):
        # returns falsey value if segment to dump not found
        cmd = [self.java_path, '-jar', self.mars_path, asm_path,
               'nc',
               self.db, self.np, render_arg('a', a, self.a),
               'mc', 'CompactDataAtZero']
        if hex_path:
            cmd += ['dump', dump_segment, 'HexText', hex_path]

        self._communicate(cmd, out_path,
                          'maybe an infinite loop' + (', see ' + out_path if out_path else '')
                          )

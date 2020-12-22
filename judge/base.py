import os, subprocess
from .utils import kill_im

timeout_default = 3

INFINITE_LOOP = '1000ffff\n00000000\n'  # beq $0, $0, -1; nop;
DISABLE_SR = '40806000\n'  # mtc0 $0


class VerificationFailed(Exception):
    pass


def render_msg(msg):
    return (', ' + msg) if msg else ''


def _communicate_callback(proc, fp, handler, timeout=None, ctx=None, raw_output_file=None):
    s = proc.communicate(timeout=timeout)[0]
    if raw_output_file:
        with open(raw_output_file, 'wb') as raw:
            raw.write(s)
    for line in s.decode(errors='ignore').splitlines():
        r = handler(line.strip()) if ctx is None else handler(line.strip(), ctx)
        if r and fp:
            fp.write(r + '\n')


class BaseRunner:
    def __init__(self, timeout=None, env=None, cwd=None,
                 kill_on_timeout=True, permit_timeout=True,
                 raw_output_file=None
                 ):
        self.timeout = timeout_default if timeout is None else timeout
        self.env = env
        self.cwd = cwd
        self.permit_timeout = permit_timeout
        self.kill_on_timeout = kill_on_timeout
        self.raw_output_file = raw_output_file

    @staticmethod
    def stop():
        pass

    def parse(self, line):
        raise TypeError

    def _communicate_fp(self, cmd, fp, timeout_msg, error_msg=None, ctx=None):
        name = self.__class__.__name__
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=self.cwd, env=self.env) as proc:
            try:
                _communicate_callback(proc, fp, self.parse, self.timeout, ctx=ctx,
                                      raw_output_file=self.raw_output_file)
            except subprocess.TimeoutExpired as e:
                proc.kill()
                if self.kill_on_timeout:
                    kill_im(os.path.basename(cmd[0]))
                _communicate_callback(proc, fp, self.parse, ctx=ctx,
                                      raw_output_file=self.raw_output_file)
                msg = '{} timed out after {} secs{}'.format(
                    name, self.timeout, render_msg(timeout_msg)
                )
                if self.permit_timeout:
                    print('Permitted:', msg)
                    return
                raise RuntimeError(msg) from e
        if proc.returncode:
            raise RuntimeError('{} subprocess returned {}{}'.format(
                name, proc.returncode, render_msg(error_msg)
            ))

    def _communicate(self, cmd, out_fn, timeout_msg=None, error_msg=None, ctx=None):
        if out_fn:
            with open(out_fn, 'w', encoding='utf-8') as fp:
                return self._communicate_fp(cmd, fp, timeout_msg, error_msg, ctx)
        return self._communicate_fp(cmd, None, timeout_msg, error_msg, ctx)


class BaseHexRunner(BaseRunner):
    def __init__(self, appendix=None, _hex_path=None, _handler_hex_path=None, **kw):
        super().__init__(**kw)
        self.appendix = appendix
        self._hex_path = _hex_path
        self._handler_hex_path = _handler_hex_path
        self.tmp_dir = None

    def _put_appendix(self, hex_path):
        if self.appendix:
            with open(hex_path, 'a', encoding='utf-8') as fp:
                fp.write('\n' + self.appendix)

    def run(self, out_path):
        raise TypeError

    # to support customized path, setter should be override and getters should return None before set
    def get_hex_path(self):
        return self._hex_path

    def get_handler_hex_path(self):
        return self._handler_hex_path

    def set_hex_path(self, path):
        raise NotImplementedError

    def set_handler_hex_path(self, path):
        raise NotImplementedError

    def _set_hex_path(self, path):
        self._hex_path = path

    def _set_handler_hex_path(self, path):
        self._handler_hex_path = path

    def set_tmp_dir(self, tmp_dir):
        self.tmp_dir = tmp_dir

    @staticmethod
    def run_loaded(out_path):
        raise TypeError

    def __call__(self, out_path):
        self._put_appendix(self.get_hex_path())
        return self.run(out_path)

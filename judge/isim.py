import os, subprocess
from .base import VerificationFailed, BaseHexRunner
from .utils import kill_im

tcl_common_fn = 'judge.cmd'
hex_common_fn = 'code.txt'
handler_hex_common_fn = 'code_handler.txt'
duration_default = '1000 us'


def get_platform(bin):
    platform = ('lin', 'nt')[os.name == 'nt']
    platform_64 = platform + '64'
    if os.path.isdir(os.path.join(bin, platform_64)):
        return platform_64
    return platform


def get_ise_path():
    if os.name != 'nt':
        return None
    from winreg import ConnectRegistry, OpenKey, EnumValue, HKEY_CLASSES_ROOT
    from shlex import split
    reg = ConnectRegistry(None, HKEY_CLASSES_ROOT)
    try:
        key = OpenKey(reg, r'isefile\shell\open\Command')
    except FileNotFoundError:
        return None
    cmd = EnumValue(key, 0)[1]
    return os.path.dirname(split(cmd)[0])


class ISim(BaseHexRunner):
    name = 'ISim'

    def __init__(self, project_path, module_name=None,
                 duration=duration_default,
                 recompile=False,
                 ise_path=None,
                 tcl_fn=tcl_common_fn,
                 **kw
                 ):
        env = os.environ.copy()
        platform_bin = None

        if 'XILINX' not in env:
            if ise_path:
                ise_path = os.path.normcase(ise_path)
            else:
                ise_path = get_ise_path()
                if not ise_path:
                    raise VerificationFailed('ISE installation not found, specify it by ise_path')
                print('Detected ISE installation at', ise_path)
            ise = ise_path if os.path.isdir(os.path.join(ise_path, 'bin')) else os.path.join(ise_path, 'ISE')
            bin = os.path.join(ise, 'bin')
            platform = get_platform(bin)
            platform_bin = os.path.join(bin, platform)

            env['XILINX'] = ise
            env['XILINX_PLATFORM'] = platform
            env['PATH'] = platform_bin + os.pathsep + env['PATH']

        exe = '.exe' if os.name == 'nt' else ''
        if module_name:
            tb_dir = project_path
            tb_basename = module_name + '_isim_beh' + exe
            tb_path = os.path.join(tb_dir, tb_basename)
        else:
            tb_dir = os.path.dirname(project_path)
            tb_basename = os.path.basename(project_path)
            tb_path = project_path

        hex_path = os.path.join(tb_dir, hex_common_fn)
        handler_hex_path = os.path.join(tb_dir, handler_hex_common_fn)
        super().__init__(**dict(kw, env=env, cwd=tb_dir,
                                _hex_path=hex_path,
                                _handler_hex_path=handler_hex_path,
                                kill_on_timeout=True))

        if not platform_bin:
            bin = os.path.join(env['XILINX'], 'bin')
            platform_bin = os.path.join(bin, get_platform(bin))

        self.exe = exe
        self.platform_bin = platform_bin
        self.recompile = recompile
        self.module_name = module_name
        self.tb_dir = tb_dir
        self.tb_basename = tb_basename
        self.tb_path = tb_path
        self.tcl_fn = tcl_fn
        self.tcl_path = os.path.join(tb_dir, tcl_fn)
        tcl_text = 'run {}\nexit\n'.format(duration.strip())
        self._generate_tcl(self.tcl_path, tcl_text)

    @staticmethod
    def _generate_tcl(path, s):
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(s)

    @staticmethod
    def parse(s):
        if 'error' in s.lower():
            raise VerificationFailed('ISim complained ' + s)
        if '$ 0' in s:
            return
        p = s.find('@')
        if p >= 0:
            return s[p:]

    def compile(self):
        self.tb_basename = tb_basename = self.module_name + '_qwqwq' + self.exe
        self.tb_path = os.path.join(self.tb_dir, tb_basename)
        subprocess.run([os.path.join(self.platform_bin, 'fuse'),
                        '--nodebug',
                        '-i', '.',
                        '--prj', self.module_name + '_beh.prj',
                        '-o', tb_basename,
                        self.module_name
                        ], env=self.env, cwd=self.tb_dir)

    def run(self, out_path):
        if self.recompile:
            self.compile()
            self.recompile = False
        self._communicate([os.path.normcase(self.tb_path), '-tclbatch', self.tcl_fn],
                          out_path,
                          'see ' + out_path,
                          'maybe ISE path is incorrect'
                          )

    def stop(self):
        kill_im(self.tb_basename)

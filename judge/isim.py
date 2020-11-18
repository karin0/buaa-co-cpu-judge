import os, os.path

from .base import \
    BaseJudge, VerificationFailed, create_tmp, mars_path_default, tmp_pre, diff_path_default, mars_timeout_default

tb_timeout_default = 5
pc_start_default = 0x3000
duration_default = '1000 us'


class ISimJudge(BaseJudge):

    def __init__(self, ise_path,
                 mars_path=mars_path_default,
                 java_path='java',
                 diff_path=diff_path_default,
                 db=False,
                 duration=duration_default,
                 pc_start=pc_start_default
                 ):
        create_tmp()
        self.ise_path = ise_path
        self.pc_start = pc_start
        self.db = db

        self.tcl_path = os.path.abspath(os.path.join(tmp_pre, 'cmd.tcl'))
        with open(self.tcl_path, 'w', encoding='utf-8') as fp:
            fp.write('run {}\nexit'.format(duration))

        ise = ise_path if os.path.isdir(os.path.join(ise_path, 'bin')) else os.path.join(ise_path, 'ISE')
        bin = os.path.join(ise, 'bin')
        platform, exe = (('lin', ''), ('nt', '.exe'))[os.name == 'nt']
        if os.path.isdir(os.path.join(bin, platform + '64')):
            platform += '64'
        platform_bin = os.path.join(bin, platform)

        self.env = env = dict(os.environ.copy(), XILINX=ise, EXE=exe, XILINX_PLATFORM=platform)
        env['PATH'] = platform_bin + os.pathsep + env['PATH']
        self.mars_path = mars_path
        self.java_path = java_path
        self.diff_path = diff_path

    @staticmethod
    def _parse(s):
        if 'error' in s.lower():
            raise VerificationFailed('ISim reported ' + s)
        if s.startswith('@'):
            return s

    def __call__(self, tb_path, asm_path,
                 tb_timeout=tb_timeout_default,
                 mars_timeout=mars_timeout_default,
                 ):
        tb_dir = os.path.dirname(tb_path)
        _, ans_fn, fix = self.call_mars(asm_path, mars_timeout, os.path.join(tb_dir, 'code.txt'), db=self.db)

        out_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + fix + '.out')
        self._communicate([tb_path, '-tclbatch', self.tcl_path],
                          out_fn, self._parse, tb_timeout,
                          'see ' + out_fn, 'ISim',
                          error_msg='maybe ISE path is incorrect ({})'.format(self.ise_path),
                          cwd=tb_dir, env=self.env, nt_kill=True
                          )
        self.diff(out_fn, ans_fn)

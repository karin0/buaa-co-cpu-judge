import os, subprocess
from .base import VerificationFailed

diff_path_default = 'fc' if os.name == 'nt' else 'diff'


class InconsistentResults(VerificationFailed):
    pass


class Diff:

    def __init__(self, diff_path=None, keep_output_files=False):
        self.diff_path = diff_path_default if diff_path is None else diff_path
        self.keep_output_files = keep_output_files

    def __call__(self, out_path, ans_path, log_path=None):
        with subprocess.Popen([self.diff_path, out_path, ans_path],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            res = proc.communicate()
            if proc.returncode:
                if log_path is None:
                    log_path = out_path + '.diff'
                with open(log_path, 'wb') as fp:
                    fp.write(res[0] + b'\n' + res[1])
                # res = res[0].decode(errors='ignore') + res[1].decode(errors='ignore')
                # print(res, file=sys.stderr)
                raise InconsistentResults('output differs, see {}, {}, and {} for diff logs'
                                          .format(out_path, ans_path, log_path))
            elif not self.keep_output_files:
                os.remove(out_path)
                os.remove(ans_path)

import os, os.path, sys, subprocess, string, argparse
import xml.etree.ElementTree as ET
from hashlib import md5
from ast import literal_eval

tmp_pre = 'tmp'
diff_fn = 'fc' if os.name == 'nt' else 'diff'

pc_width_default = 32
pc_by_word_default = False
pc_start_default = 0
dma_width_default = 5
dma_by_word_default = False
logisim_timeout_default = 1
mars_timeout_default = 1
mars_path_default = os.path.join(os.path.dirname(__file__), 'kits', 'Mars_Changed.jar')

hex_chars = set(filter(lambda c: not c.isupper(), string.hexdigits))
def to_instr(line):
    if not line:
        return None
    for ch in line:
        if ch not in hex_chars:
            return None
    r = line.lstrip('0')
    return r if r else '0'

def to_hex(x):
    return hex(x)[2:].zfill(8)

def to_dec(x):
    return str(x).rjust(2)


class LogLine:

    def __init__(self, line):
        self.s = ''.join(line.split())
        for ch in self.s:
            if ch not in ('0', '1'):
                raise ValueError('Bad output: ' + line)
        self.p = 0

    def take(self, n, by_word=False):
        self.p += n
        r = int(self.s[self.p - n : self.p], 2)
        if by_word:
            r *= 4
        return r

    def take_hex(self, n, by_word=False):
        return to_hex(self.take(n, by_word))

    def parse(self,
        pc_width=pc_width_default,
        pc_by_word=pc_by_word_default,
        pc_start=pc_start_default,
        dma_width=dma_width_default,
        dma_by_word=dma_by_word_default
    ):
        pc = to_hex(0x3000 - pc_start + self.take(pc_width, pc_by_word))
        gw = self.take(1)
        ga_int = self.take(5)
        ga = to_dec(ga_int)
        gd = self.take_hex(32)
        if gw and ga_int:
            return '@{}: ${} <= {}'.format(pc, ga, gd)

        if self.take(1):
            da = self.take_hex(dma_width, dma_by_word)
            return '@{}: *{} <= {}'.format(pc, da, self.take_hex(32))
        return None

def gen_cpu(circ_path, prog_hex_fn, ifu_circ_name):
    tree = ET.parse(circ_path)
    root = tree.getroot()
    if ifu_circ_name is None:
        cont = root.find('./circuit/comp[@name="ROM"]/a[@name="contents"]')
    else:
        cont = root.find('./circuit[@name="{' + ifu_circ_name + '"]/comp[@name="ROM"]/a[@name="contents"]')
    if cont is None:
        raise ValueError('no rom comp found for ' + circ_path)

    s = cont.text
    desc = s[:s.find('\n')]
    addr_width, data_width = map(int, desc[desc.find(':') + 1:].split())
    if data_width != 32:
        raise ValueError('data width of rom is ' + str(data_width) + ', 32 expected')
    max_ins_cnt = 2 ** addr_width

    with open(prog_hex_fn, 'r', encoding='utf-8') as fp:
        prog = fp.read()

    with open('-image'.join(os.path.splitext(prog_hex_fn)), 'w', encoding='utf-8') as fp:
        fp.write('v2.0 raw\n' + prog)

    instrs = []
    for s in prog.splitlines():
        ins = to_instr(s)
        if ins:
            instrs.append(ins)
            if len(instrs) > max_ins_cnt:
                raise ValueError('too many instructions for rom addr width ' + str(addr_width))

    while instrs and instrs[-1] == '0':
        instrs.pop()

    lines = [desc]
    line = []
    for ins in instrs:
        line.append(ins)
        if len(line) == 8:
            lines.append(' '.join(line))
            line.clear()
    if line:
        lines.append(' '.join(line))
    cont.text = '\n'.join(lines) + '\n'
    ha = md5(prog.encode('utf-8')).hexdigest()[:10]
    new_circ_path = os.path.join(tmp_pre, ('-' + ha).join(os.path.splitext(os.path.basename(circ_path))))
    tree.write(new_circ_path)
    return new_circ_path

class Judge:

    class VerificationFailed(Exception):
        pass

    def __init__(self, logisim_path, mars_path=mars_path_default,
        java_path='java',
        pc_width=pc_width_default,
        pc_by_word=pc_by_word_default,
        pc_start=pc_start_default,
        dma_width=dma_width_default,
        dma_by_word=dma_by_word_default,
        ):
        if not os.path.isdir(tmp_pre):
            os.mkdir(tmp_pre)

        self.logisim_path = logisim_path
        self.mars_path = mars_path
        self.java_path = java_path

        self.pc_width = pc_width
        self.pc_by_word = pc_by_word
        self.pc_start = pc_start
        self.dma_width = dma_width
        self.dma_by_word = dma_by_word

    @staticmethod
    def _mars_communicate(proc, fp, timeout=None):
        for line in proc.communicate(timeout=timeout)[0].splitlines():
            s = line.decode().strip()
            if s.startswith('@'):
                fp.write(s + '\n')

    def _logisim_communicate(self, proc, fp, timeout=None):
        for line in proc.communicate(timeout=timeout)[0].splitlines():
            s = line.decode().strip()
            try:
                r = LogLine(s).parse(
                    self.pc_width, self.pc_by_word, self.pc_start,
                    self.dma_width, self.dma_by_word
                )
            except ValueError:
                raise Judge.VerificationFailed('invalid circuit output: ' + s)
            if r:
                fp.write(r + '\n')

    @staticmethod
    def _call(cmd, out_fn, handler, timeout, timeout_msg, error_meta):
        with open(out_fn, 'w', encoding='utf-8') as fp:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
                try:
                    handler(proc, fp, timeout)
                except subprocess.TimeoutExpired as e:
                    proc.kill()
                    handler(proc, fp)
                    raise Judge.VerificationFailed(timeout_msg.format(timeout)) from e
                if proc.returncode:
                    raise Judge.VerificationFailed(error_meta + ' subprocess returned ' + str(proc.returncode))

    def __call__(self, circ_path, asm_path,
        ifu_circ_name=None,
        logisim_timeout=logisim_timeout_default,
        mars_timeout=mars_timeout_default
        ):
        hex_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.hex')
        ans_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.ans')
        self._call([self.java_path, '-jar', self.mars_path, asm_path,
                'nc', 'mc', 'CompactDataAtZero', 'dump', '.text', 'HexText', hex_fn],
            ans_fn, self._mars_communicate, mars_timeout,
            'MARS simulation timed out (> {} secs), maybe an infinite loop, see ' + ans_fn, 'MARS'
        )

        circ_path = gen_cpu(circ_path, hex_fn, ifu_circ_name)
        out_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.out')
        self._call([self.java_path, '-jar', self.logisim_path, circ_path, '-tty', 'table'],
            out_fn, self._logisim_communicate, logisim_timeout,
            'Logisim circuit timed out (> {} secs) before halting, see ' + out_fn, 'Logisim'
        )

        if subprocess.run([diff_fn, out_fn, ans_fn]).returncode:
            raise Judge.VerificationFailed('output differs, see {} and {}'.format(out_fn, ans_fn))

def dump_self():
    with open(__file__, 'rb') as inf, \
         open(__file__ + '.hex', 'w', encoding='utf-8') as outf:
        outf.write('v2.0 raw\n' + inf.read().hex('\n', 4) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='verify MIPS CPU circuits in Logisim against MARS simulation of given .asm program.')
    parser.add_argument('circ_path', help='path to your Logisim project file')
    parser.add_argument('asm_path', help='path to the .asm program to load into circuit and run in MARS')
    parser.add_argument('logisim_path', help='path to local Logisim .jar file')
    parser.add_argument('mars_path', nargs='?', help='path to local MARS .jar file, "kits/Mars_Changed.jar" by default',
                        default=mars_path_default)
    parser.add_argument('--java_path', metavar='path',
                        default='java', help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--ifu_circ_name', metavar='ifu',
                        default=None, help='name of the circuit containing the ROM to load dumped instructions, omit to find in the whole project')
    parser.add_argument('--pc_width', metavar='width',
                        default=pc_width_default, help='width of output PC, {} by default'.format(pc_by_word_default))
    parser.add_argument('--pc_start', metavar='addr',
                        default=str(pc_start_default), help='starting address of output PC, {} by default'.format(hex(pc_start_default)))
    parser.add_argument('--pc_by_word', action='store_true',
                        help='specify this if output PC is word addressing')
    parser.add_argument('--dm_addr_width', metavar='width',
                        default=dma_width_default, help='width of DM_WRITE_ADDRESS in output, {} by default'.format(dma_width_default))
    parser.add_argument('--dm_addr_by_word', action='store_true',
                        help='specify this if output DM address is word addressing')
    parser.add_argument('--logisim_timeout', metavar='secs',
                        default=logisim_timeout_default, help='timeout for Logisim simulation, {} by default'.format(logisim_timeout_default))
    parser.add_argument('--mars_timeout', metavar='secs',
                        default=mars_timeout_default, help='timeout for MARS simulation, {} by default'.format(mars_timeout_default))

    args = parser.parse_args()
    judge = Judge(args.logisim_path, args.mars_path, args.java_path,
        args.pc_width, args.pc_by_word, int(literal_eval(args.pc_start)),
        args.dm_addr_width, args.dm_addr_by_word)
    try:
        judge(args.circ_path, args.asm_path, args.ifu_circ_name, args.logisim_timeout, args.mars_timeout)
    except Judge.VerificationFailed as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print('ok')

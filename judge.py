import os, os.path, sys, subprocess, string, argparse
import xml.etree.ElementTree as ET
from hashlib import md5

tmp_pre = 'tmp'
diff_fn = 'fc' if os.name == 'nt' else 'diff'

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
                raise RuntimeError('Bad output: ' + line)
        self.p = 0

    def take(self, n):
        self.p += n
        return int(self.s[self.p - n : self.p], 2)

    def take_hex(self, n):
        return to_hex(self.take(n))

    def parse(self, pc_width=32, dma_width=32, pc_by_word=False, dma_by_word=False):
        pc = self.take(pc_width)
        if pc_by_word:
            pc = 0x3000 + pc * 4
        pc = to_hex(pc)

        gw = self.take(1)
        ga_int = self.take(5)
        ga = to_dec(ga_int)
        gd = self.take_hex(32)
        if gw and ga_int:
            return '@{}: ${} <= {}'.format(pc, ga, gd)

        dw = self.take(1)
        if dw:
            da = self.take(dma_width)
            if dma_by_word:
                da *= 4
            da = to_hex(da)
            dd = self.take_hex(32)
            return '@{}: *{} <= {}'.format(pc, da, dd)
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

    def __init__(self, logisim_path, mars_path='kits/Mars_Changed.jar',
        java_path='java',
        pc_width=32,
        dma_width=32,
        pc_by_word=False,
        dma_by_word=False
        ):
        if not os.path.isdir(tmp_pre):
            os.mkdir(tmp_pre)

        self.logisim_path = logisim_path
        self.mars_path = mars_path
        self.java_path = java_path

        self.pc_width = pc_width
        self.dma_width = dma_width
        self.pc_by_word = pc_by_word
        self.dma_by_word = dma_by_word

    def __call__(self, circ_path, asm_path, ifu_circ_name=None):
        hex_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.hex')
        ans_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.ans')

        with open(ans_fn, 'w', encoding='utf-8') as fp:
            with subprocess.Popen(
                [self.java_path, '-jar', self.mars_path, asm_path,
                    'mc', 'CompactDataAtZero', 'dump', '.text', 'HexText', hex_fn],
                stdout=subprocess.PIPE) as proc:
                for line in proc.stdout:
                    s = line.decode()
                    if s.startswith('@'):
                        fp.write(s)
            if proc.returncode:
                raise RuntimeError('MARS process returned ' + str(proc.returncode))

        circ_path = gen_cpu(circ_path, hex_fn, ifu_circ_name)
        out_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + '.out')
        with open(out_fn, 'w', encoding='utf-8') as fp:
            with subprocess.Popen([self.java_path, '-jar', self.logisim_path, circ_path, '-tty', 'table'], stdout=subprocess.PIPE) as proc:
                for line in proc.stdout:
                    r = LogLine(line.decode()).parse(self.pc_width, self.dma_width, self.pc_by_word, self.dma_by_word)
                    if r:
                        fp.write(r + '\n')
            if proc.returncode:
                raise RuntimeError('Logisim process returned ' + str(proc.returncode))

        return subprocess.run([diff_fn, out_fn, ans_fn]).returncode


def dump_self():
    with open(__file__, 'rb') as inf, \
         open(__file__ + '.hex', 'w', encoding='utf-8') as outf:
        outf.write('v2.0 raw\n' + inf.read().hex('\n', 4) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run your CPU in Logisim and compare with results from MARS.')
    parser.add_argument('circ_path', help='path to your Logisim project file')
    parser.add_argument('asm_path', help='path to the .asm program to load into circuit and run in MARS')
    parser.add_argument('logisim_path', help='path to local Logisim .jar file')
    parser.add_argument('mars_path', nargs='?', help='path to local MARS .jar file, "kits/Mars_Changed.jar" by default',
                        default='kits/Mars_Changed.jar')
    parser.add_argument('--java_path', metavar='path',
                        default='java', help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--ifu_circ_name', metavar='ifu',
                        default=None, help='name of the circuit containing the ROM to load dumped instructions, omit to search in all circuits')
    parser.add_argument('--pc_width', metavar='width',
                        default=32, help='width of PC in CPU output, 32 by default')
    parser.add_argument('--dm_addr_width', metavar='width',
                        default=32, help='width of written DM address in output, 32 by default')
    parser.add_argument('--pc_by_word', action='store_true',
                        help='specify this if output PC is word addressing (0, 1, 2, ..), otherwise it should be compatible with MARS (0x3000, 0x3004, ...)')
    parser.add_argument('--dm_addr_by_word', action='store_true',
                        help='specify this if output DM address is word addressing')

    args = parser.parse_args()
    judge = Judge(args.logisim_path, args.mars_path, args.java_path, args.pc_width, args.dm_addr_width, args.pc_by_word, args.dm_addr_by_word)
    if judge(args.circ_path, args.asm_path, args.ifu_circ_name):
        print('Differs!', file=sys.stderr)
        sys.exit(1)

import os, os.path, string
import xml.etree.ElementTree as ET

from .base import BaseJudge, VerificationFailed, tmp_pre, diff_path_default, mars_path_default, create_tmp, mars_timeout_default

diff_path_default = 'fc' if os.name == 'nt' else 'diff'

pc_width_default = 32
pc_by_word_default = False
pc_start_default = 0
dma_width_default = 32
dma_by_word_default = False
logisim_timeout_default = 3

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
                raise ValueError('found ' + ch)
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

def gen_cpu(circ_path, prog_hex_fn, ifu_circ_name, fix):
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
        raise ValueError('too many instructions ({}) for rom addr width {}'.format(len(instrs), addr_width))

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
    new_circ_path = os.path.join(tmp_pre, fix.join(os.path.splitext(os.path.basename(circ_path))))
    tree.write(new_circ_path)
    return new_circ_path

class LogisimJudge(BaseJudge):

    class IllegalCircuit(VerificationFailed):
        pass

    def __init__(self, logisim_path, mars_path=mars_path_default,
        java_path='java',
        diff_path=diff_path_default,
        pc_width=pc_width_default,
        pc_by_word=pc_by_word_default,
        pc_start=pc_start_default,
        dma_width=dma_width_default,
        dma_by_word=dma_by_word_default,
        ):
        create_tmp()

        self.logisim_path = logisim_path
        self.mars_path = mars_path
        self.java_path = java_path
        self.diff_path = diff_path

        self.pc_width = pc_width
        self.pc_by_word = pc_by_word
        self.pc_start = pc_start
        self.dma_width = dma_width
        self.dma_by_word = dma_by_word

    def _parse(self, s):
        try:
            r = LogLine(s).parse(
                self.pc_width, self.pc_by_word, self.pc_start,
                self.dma_width, self.dma_by_word
            )
        except ValueError as e:
            raise VerificationFailed('invalid circuit output ({}): {}'.format(e, s)) from e
        return r

    def __call__(self, circ_path, asm_path,
        ifu_circ_name=None,
        logisim_timeout=logisim_timeout_default,
        mars_timeout=mars_timeout_default
        ):
        hex_fn, ans_fn, fix = self.call_mars(asm_path, mars_timeout)

        try:
            circ_path = gen_cpu(circ_path, hex_fn, ifu_circ_name, fix)
        except ValueError as e:
            raise self.IllegalCircuit(e) from e
        out_fn = os.path.join(tmp_pre, os.path.basename(asm_path) + fix + '.out')
        self._communicate([self.java_path, '-jar', self.logisim_path, circ_path, '-tty', 'table'],
            out_fn, self._parse, logisim_timeout,
            'maybe halt is incorrect, see ' + out_fn, 'Logisim'
        )

        self.diff(out_fn, ans_fn)

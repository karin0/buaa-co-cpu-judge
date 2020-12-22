import os, os.path, string
import xml.etree.ElementTree as ET

from .base import BaseHexRunner, VerificationFailed

pc_width_default = 32
pc_by_word_default = False
pc_start_default = 0
dma_width_default = 32
dma_by_word_default = False

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
        r = int(self.s[self.p - n: self.p], 2)
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


def gen(circ_path, hex_path, im_circ_name, tmp_dir):
    tree = ET.parse(circ_path)
    root = tree.getroot()
    if im_circ_name is None:
        token = './circuit/comp[@name="ROM"]/a[@name="contents"]'
    else:
        token = './circuit[@name="{' + im_circ_name + '"]/comp[@name="ROM"]/a[@name="contents"]'
    cont = root.find(token)
    if cont is None:
        raise ValueError('no rom comp found in ' + circ_path)

    s = cont.text
    desc = s[:s.find('\n')]
    addr_width, data_width = map(int, desc[desc.find(':') + 1:].split())
    if data_width != 32:
        raise ValueError('data width of the rom is ' + str(data_width) + ', 32 expected')
    max_ins_cnt = 2 ** addr_width

    with open(hex_path, 'r', encoding='utf-8') as fp:
        hex = fp.read()

    image_path = os.path.join(tmp_dir, os.path.splitext(os.path.basename(hex_path))[0] + '-image.hex')
    with open(image_path, 'w', encoding='utf-8') as fp:
        fp.write('v2.0 raw\n' + hex)

    instrs = []
    for s in hex.splitlines():
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

    new_circ_path = os.path.join(tmp_dir, os.path.basename(circ_path))
    tree.write(new_circ_path)
    return new_circ_path


class IllegalCircuit(VerificationFailed):
    pass


class Logisim(BaseHexRunner):

    def __init__(self, circ_path,
                 logisim_path,
                 java_path='java',
                 pc_width=pc_width_default,
                 pc_by_word=pc_by_word_default,
                 pc_start=pc_start_default,
                 dma_width=dma_width_default,
                 dma_by_word=dma_by_word_default,
                 im_circuit_name=None,
                 **kw
                 ):
        super().__init__(**kw)

        self.circ_path = circ_path
        self.logisim_path = logisim_path
        self.java_path = java_path

        self.im_circ_name = im_circuit_name
        self.pc_width = pc_width
        self.pc_by_word = pc_by_word
        self.pc_start = pc_start
        self.dma_width = dma_width
        self.dma_by_word = dma_by_word

    def parse(self, s):
        if not s:
            return
        try:
            r = LogLine(s).parse(
                self.pc_width, self.pc_by_word, self.pc_start,
                self.dma_width, self.dma_by_word
            )
        except ValueError as e:
            raise VerificationFailed('invalid output ({}): {}'.format(e, s)) from e
        return r

    def set_hex_path(self, path):
        self._set_hex_path(path)

    def run(self, out_path):
        try:
            circ_path = gen(self.circ_path, self.get_hex_path(), self.im_circ_name, self.tmp_dir())
        except ValueError as e:
            raise IllegalCircuit(e) from e
        self._communicate([self.java_path, '-jar', self.logisim_path, circ_path, '-tty', 'table'],
                          out_path,
                          'maybe the halt pin is set incorrectly, see ' + out_path
                          )

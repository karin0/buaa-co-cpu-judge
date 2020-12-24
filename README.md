This is inspired by [
BUAA-CO-Logisim-Judger](https://github.com/biopuppet/BUAA-CO-Logisim-Judger).

This helps to verify MIPS CPU in Logisim circuits or Verilog HDL against MARS simulation based on given .asm programs.

## Getting started

### Logisim

Set up the output pins in your `main` circuit in order of PC (32-bit by default), GRF_WRITE_ENABLED (1-bit), GRF_WRITE_ADDRESS (5-bit), GRF_WRITE_DATA (32-bit), DM_WRITE_ENABLED (1-bit), DM_WRITE_ADDRESS (32-bit by default), and DM_WRITE_DATA (32-bit). Dumped instructions for verification will be loaded into the ROM component automatically.

### Verilog (ISim)

Your test bench should instantiate the CPU and provide clocks. At initialization or reset, it should `$readmemh` from `code.txt` into the instruction memory and `$display` writing accesses as the course requires.

## Usage

### CLI

#### Logisim

```shell
$ python logisim-judge.py mips.circ mips1.asm kits/logisim.jar --dm-address-width 5 --dm-address-by-word
```

```shell
$ python logisim-judge.py --help
```

#### Verilog (ISim)

```shell
$ python isim-judge.py ise-projects/mips4 tb mips1.asm --recompile
```
Unless the switch `--recompile` is specified, latest changes on the sources may not take effect before a manual ISim simulation.

```shell
$ python isim-judge.py ise-projects/mips5 tb mips1.asm --db
```
The switch `--db` enables delayed branching for MARS.

```shell
$ python isim-judge.py --help
```

### Python APIs

Refer to [example.py](example.py) for a useful wheel.

#### Example

```python
from judge import Mars, ISim, Logisim, MarsJudge, DuetJudge, resolve_paths, INFINITE_LOOP

isim = ISim('ise-projects/mips5', 'tb', appendix=INFINITE_LOOP)
mars = Mars(db=True)
judge = MarsJudge(isim, mars)

judge('mips1.asm')
judge.all(['mips1.asm', 'mips2.asm'])
judge.all(resolve_paths('./cases'))
judge.all(resolve_paths(['./cases', './extra-cases', 'mips1.asm']))

logisim = Logisim('mips.circ', 'kits/logisim.jar', appendix=INFINITE_LOOP)
naive_mars = Mars()
judge = MarsJudge(logisim, naive_mars)
judge('mips1.asm')

isim = ISim('ise-projects/mips7', 'tb', appendix=INFINITE_LOOP)
judge = MarsJudge(isim, mars)
judge.load_handler('handler.asm')
judge('exceptions.asm')

std = ISim('ise-projects/mips-std', 'tb', appendix=INFINITE_LOOP)
judge = DuetJudge(isim, std, mars)
judge('interrupts.asm')  # Dui Pai
```

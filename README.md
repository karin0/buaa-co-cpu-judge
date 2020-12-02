This is inspired by [
BUAA-CO-Logisim-Judger](https://github.com/biopuppet/BUAA-CO-Logisim-Judger).

This helps to verify MIPS CPU in Logisim circuits or Verilog HDL against MARS simulation behaviours of some .asm program.

## Getting started

A modified version of MARS which outputs writing accesses is required and distributed in this repo.

### Logisim

Set up the output pins in your `main` circuit in order of PC (32-bit by default), GRF_WRITE_ENABLED (1-bit), GRF_WRITE_ADDRESS (5-bit), GRF_WRITE_DATA (32-bit), DM_WRITE_ENABLED (1-bit), DM_WRITE_ADDRESS (32-bit by default), DM_WRITE_DATA (32-bit), and halt (1-bit). The output pin labelled "halt" should be pulled to 1 if the entire program is about to finish (i. e. the IM address will overflow in the **next** cycle, so other outputs are **not** ignored when halt is 1), and all the other pins are not required to be labelled. Dumped instructions for verification will be loaded into the ROM component automatically.

### Verilog

Your test bench should provide clocks and drive the CPU. At runtime, it should `$readmemh` from `code.txt` into IM and `$display` writing accesses in the same format as the course requires. Simulate the test bench in ISim manually for once to ensure the compiled test bench executable is generated in your ISE project directory.

## Usage

### CLI

#### Logisim

```shell
$ python logisim-judge.py p3.circ test.asm kits/logisim.jar --dm_addr_width 5 --dm_addr_by_word
```

This loads dumpped instructions into the Logisim project, runs MARS and Logisim simulations and compares the outputs. Both output files can be found in `./tmp` directory.

```shell
$ python logisim-judge.py --help
```

This shows extra options.

#### Verilog

```shell
$ python isim-judge.py ise-projects/mips/tb_isim_beh.exe test.asm "C:\Xilinx\14.7\ISE_DS"
```

```shell
$ python isim-judge.py ise-projects/mips5/tb_isim_beh.exe test.asm "C:\Xilinx\14.7\ISE_DS" --db
```
This enables delayed branching when calling MARS.

```shell
$ python isim-judge.py --help
```

### Python APIs

- `class LogisimJudge(logisim_path, mars_path='kits/Mars_Changed.jar', java_path='java', diff_path='fc' if os.name == 'nt' else 'diff', pc_width=32, pc_by_word=False, pc_start=0x0000, dma_width=32, dma_by_word=False)`

- `LogisimJudge.__call__(circ_path, asm_path, ifu_circ_name=None, logisim_timeout=3, mars_timeout=3)`

- `class ISimJudge(tb_path, ise_path, mars_path='kits/Mars_Changed.jar', java_path='java', diff_path='fc' if os.name == 'nt' else 'diff', db=False, np=False, duration='1000 us', pc_start=0x3000)`

- `ISimJudge.__call__(asm_path, tb_timeout=5, mars_timeout=3, keep_output_files=False)`

- `ISimJudge.all(asm_paths, fn_wire, tb_timeout=5, mars_timeout=3, keep_output_files=False, workers_num=None, on_success=None, on_error=None, kill_on_error=False, stop_on_error=True)`

- `class VerificationFailed(Exception)`

#### Example

```python
import sys
from judge import LogisimJudge, ISimJudge, VerificationFailed

judge3 = LogisimJudge('kits/logisim-generic-2.7.1.jar')
judge4 = ISimJudge('ise-projects/mips/tb_isim_beh.exe', r'C:\Xilinx\14.7\ISE_DS')
try:
    judge3('p3.circ', 'mips1.asm')
    judge4('mips1.asm')
    judge4.all(['cases/mips1.asm', 'cases/mips2.asm', 'cases/mips3.asm'], '/uut/ifu/fn')
except VerificationFailed as e:
    print('failed qwq:', e, file=sys.stderr)
    sys.exit(1)
```

This is inspired by [
BUAA-CO-Logisim-Judger](https://github.com/biopuppet/BUAA-CO-Logisim-Judger).

This helps to verify MIPS CPU circuits in Logisim against behaviours from MARS simulation of given .asm program.

### Usage

#### Setting up

Set the output pins in your `main` circuit in order of PC (32-bit by default), GRF_WRITE_ENABLED (1-bit), GRF_WRITE_ADDRESS (5-bit), GRF_WRITE_DATA (32-bit), DM_WRITE_ENABLED (1-bit), DM_WRITE_ADDRESS (5-bit by default), DM_WRITE_DATA (32-bit), and halt (1-bit). The output pin labelled "halt" should be pulled to 1 if the entire program is about to finish (i. e. the IM address will overflow in the **next** cycle, so other outputs are not ignored when halt is 1), and all the other pins are not required to be labelled. Dumped instructions for verification will be loaded into the ROM component automatically.

#### CLI

```shell
$ python judge.py p3.circ test.asm somewhere/logisim.jar --dm_addr_width 5 --dm_addr_by_word
```

This loads dumpped instructions into the Logisim project, runs MARS and Logisim simulations and checks the output. Both output files can be found in folder `./tmp`.

A modified version of MARS which outputs all writing accesses is required, and also provided in this repo.

```
$ python judge.py --help
```
This shows extra options of the CLI tool.

#### Python APIs

- `class Judge(logisim_path, mars_path='kits/Mars_Changed.jar', java_path='java', pc_width=32, pc_by_word=False, pc_start=0x0000, dma_width=5, dma_by_word=False)`

- `Judge.__call__(circ_path, asm_path, ifu_circ_name=None, logisim_timeout=1, mars_timeout=1)`

##### Example

```python
import sys
from judge import Judge

judge = Judge('../logisim-generic-2.7.1.jar')
try:
    judge('p3.circ', 'mips1.asm')
except Judge.VerificationFailed as e:
    print('failed qwq:', e, file=sys.stderr)
    sys.exit(1)
```

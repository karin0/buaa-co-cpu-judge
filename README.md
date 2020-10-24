This is inspired by [
BUAA-CO-Logisim-Judger](https://github.com/biopuppet/BUAA-CO-Logisim-Judger).

This helps to assemble and run your .asm program with MARS, load dumped instructions into the ROM in your circuit, simulate it with Logisim and compare the results with output from MARS.

### Usage

First, set up output pins in your `main` circuit in order of PC (32-bit by default), GRF_WRITE_ENABLED (1-bit), GRF_WRITE_ADDRESS (5-bit), GRF_WRITE_DATA (32-bit), DM_WRITE_ENABLED (1-bit), DM_WRITE_ADDRESS (32-bit by default), DM_WRITE_DATA (32-bit), and halt (1-bit). The output pin labelled "halt" should be pulled to 1 when the entire program has finished, and labels of all the other pins are optional.

GRF_WRITE_ADDRESS and GRF_WRITE_DATA are ignored when judging if GRF_WRITE_ENABLED or GRF_WRITE_ADDRESS outputs 0, and the same goes for DM.

#### CLI

```shell
$ python judge.py p3.circ test.asm somewhere/logisim.jar kits/Mars_Changed.jar
```

A modified version of MARS which outputs all writing accesses is required, and also provided in this repo.

```
$ python judge.py --help
```
This shows extra options from CLI.

#### Python APIs

- `class Judge(logisim_path, mars_path='kits/Mars_Changed.jar', java_path='java', pc_width=32, dma_width=32, pc_by_word=False, dma_by_word=False)`

- `Judge.__call__(circ_path, asm_path, ifu_circ_name=None)`

##### Example

```python
import sys
from judge import Judge

judge = Judge('../logisim-generic-2.7.1.jar')
if judge('p3.circ', 'mips1.asm'):
    print('failed qwq', file=sys.stderr)
```

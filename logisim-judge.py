import argparse
from judge.logisim import *
from judge.base import timeout_default
from judge import Logisim, Mars, Diff, MarsJudge, INFINITE_LOOP, resolve_paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify MIPS CPU circuits in Logisim against MARS simulation of '
                                                 'given .asm program.')
    parser.add_argument('circuit_path',
                        help='path to the Logisim project file')
    parser.add_argument('asm_path',
                        help='path to the .asm program to simulate, or a directory containing multiple .asm files')
    parser.add_argument('logisim_path',
                        help='path to the Logisim .jar file')
    parser.add_argument('--mars-path',
                        help='path to the modified MARS .jar file, the built-in one by default',
                        default=None)
    parser.add_argument('--java-path', metavar='path',
                        default='java',
                        help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--diff-path', metavar='path',
                        default=None,
                        help='path to your diff tool, "diff" for POSIX and "fc" for Windows by default')
    parser.add_argument('--im-circuit-name', metavar='im',
                        default=None,
                        help='name of the circuit containing the ROM to load dumped instructions into, omit to look'
                             ' for any ROM in the project')
    parser.add_argument('--pc-width', metavar='width', type=int,
                        default=pc_width_default, help='width of output PC, {} by default'.format(pc_by_word_default))
    parser.add_argument('--pc-start', metavar='addr', type=int,
                        default=str(pc_start_default),
                        help='starting address of output PC, {} by default'.format(hex(pc_start_default)))
    parser.add_argument('--pc-by-word', action='store_true',
                        help='specify this if output PC is word addressing')
    parser.add_argument('--dm-address-width', metavar='width', type=int,
                        default=dma_width_default,
                        help='width of DM_WRITE_ADDRESS in output, {} by default'.format(dma_width_default))
    parser.add_argument('--dm-address-by-word', action='store_true',
                        help='specify this if output DM address is word addressing')
    parser.add_argument('--no-infinite-loop-appendix', action='store_true',
                        help='specify this to prevent an extra infinite loop inserted at the end of simulation, '
                             'where you have to provide a halt output pin in your project')
    parser.add_argument('--logisim-timeout', metavar='secs', type=int,
                        default=None,
                        help='timeout for Logisim simulation, {} by default'.format(timeout_default))
    parser.add_argument('--mars-timeout', metavar='secs', type=int,
                        default=None,
                        help='timeout for MARS simulation, {} by default'.format(timeout_default))

    args = parser.parse_args()
    logi = Logisim(args.circuit_path, args.logisim_path, args.java_path,
                   args.pc_width, args.pc_by_word, args.pc_start,
                   args.dm_address_width, args.dm_address_by_word,
                   args.im_circuit_name,
                   appendix=None if args.no_infinite_loop_appendix else INFINITE_LOOP,
                   timeout=args.logisim_timeout
                   )

    mars = Mars(args.mars_path, java_path=args.java_path, timeout=args.mars_timeout)
    diff = Diff(args.diff_path)

    judge = MarsJudge(logi, mars)
    judge.all(resolve_paths(args.asm_path))

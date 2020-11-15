import sys, argparse
from judge.logisim import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify MIPS CPU circuits in Logisim against MARS simulation of '
                                                 'given .asm program.')
    parser.add_argument('circ_path',
                        help='path to the Logisim project file')
    parser.add_argument('asm_path',
                        help='path to the .asm program to simulate')
    parser.add_argument('logisim_path',
                        help='path to the Logisim .jar file')
    parser.add_argument('mars_path', nargs='?',
                        help='path to the modified MARS .jar file, "kits/Mars_Changed.jar" by default',
                        default=mars_path_default)
    parser.add_argument('--java_path', metavar='path',
                        default='java',
                        help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--diff_path', metavar='path',
                        default=diff_path_default,
                        help='path to your diff tool, "diff" for POSIX and "fc" for win32 by default')
    parser.add_argument('--ifu_circ_name', metavar='ifu',
                        default=None,
                        help='name of the circuit containing the ROM to load dumped instructions into, omit to find '
                             'in the whole project')
    parser.add_argument('--pc_width', metavar='width', type=int,
                        default=pc_width_default, help='width of output PC, {} by default'.format(pc_by_word_default))
    parser.add_argument('--pc_start', metavar='addr', type=int,
                        default=str(pc_start_default),
                        help='starting address of output PC, {} by default'.format(hex(pc_start_default)))
    parser.add_argument('--pc_by_word', action='store_true',
                        help='specify this if output PC is word addressing')
    parser.add_argument('--dm_addr_width', metavar='width', type=int,
                        default=dma_width_default,
                        help='width of DM_WRITE_ADDRESS in output, {} by default'.format(dma_width_default))
    parser.add_argument('--dm_addr_by_word', action='store_true',
                        help='specify this if output DM address is word addressing')
    parser.add_argument('--logisim_timeout', metavar='secs', type=int,
                        default=logisim_timeout_default,
                        help='timeout for Logisim simulation, {} by default'.format(logisim_timeout_default))
    parser.add_argument('--mars_timeout', metavar='secs', type=int,
                        default=mars_timeout_default,
                        help='timeout for MARS simulation, {} by default'.format(mars_timeout_default))

    args = parser.parse_args()
    judge = LogisimJudge(args.logisim_path, args.mars_path, args.java_path, args.diff_path,
                         args.pc_width, args.pc_by_word, args.pc_start,
                         args.dm_addr_width, args.dm_addr_by_word)
    try:
        judge(args.circ_path, args.asm_path, args.ifu_circ_name, args.logisim_timeout, args.mars_timeout)
    except VerificationFailed as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print('ok')

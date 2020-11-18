import sys, argparse
from judge.isim import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify MIPS CPU in Verilog against MARS simulation of given .asm '
                                                 'program.')
    parser.add_argument('tb_path',
                        help='path to the ISim test bench executable, e. g. "./projects/mips/tb_isim_beh(.exe)"')
    parser.add_argument('asm_path',
                        help='path to the .asm program to simulate')
    parser.add_argument('ise_path',
                        help=r'path to the ISE installation directory, e. g. "/opt/Xilinx/14.7/ISE_DS" or '
                             r'"C:\Xilinx\14.7\ISE_DS"')
    parser.add_argument('mars_path', nargs='?',
                        help='path to the modified MARS .jar file, "kits/Mars_Changed.jar" by default',
                        default=mars_path_default)
    parser.add_argument('--java_path', metavar='path',
                        default='java', help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--diff_path', metavar='path',
                        default=diff_path_default,
                        help='path to your diff tool, "diff" for POSIX and "fc" for win32 by default')
    parser.add_argument('--pc_start', metavar='addr', type=int,
                        default=str(pc_start_default),
                        help='starting address of PC, {} by default'.format(hex(pc_start_default)))
    parser.add_argument('--db', action='store_true',
                        help='specify this to enable delayed branching')
    parser.add_argument('--duration', metavar='time',
                        default=duration_default,
                        help='duration for ISim simulation, "{}" by default'.format(duration_default))
    parser.add_argument('--tb_timeout', metavar='secs', type=int,
                        default=tb_timeout_default,
                        help='timeout for ISim simulation, {} by default'.format(tb_timeout_default))
    parser.add_argument('--mars_timeout', metavar='secs', type=int,
                        default=mars_timeout_default,
                        help='timeout for MARS simulation, {} by default'.format(mars_timeout_default))

    args = parser.parse_args()
    judge = ISimJudge(args.ise_path, args.mars_path, args.java_path, args.diff_path, args.db,
                      args.duration, args.pc_start)
    try:
        judge(args.tb_path, args.asm_path, args.tb_timeout, args.mars_timeout)
    except VerificationFailed as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print('ok')

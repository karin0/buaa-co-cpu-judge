import argparse
from judge.isim import duration_default
from judge.base import timeout_default
from judge import ISim, Mars, Diff, MarsJudge, INFINITE_LOOP, resolve_paths

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify MIPS CPU in Verilog against MARS simulation of given .asm '
                                                 'program.')
    parser.add_argument('project_path',
                        help='path to your ISE project')
    parser.add_argument('module_name',
                        help='name of your test bench module')
    parser.add_argument('asm_path',
                        help='path to the .asm program to simulate, or a directory containing multiple .asm files')
    parser.add_argument('--ise-path',
                        help=r'path to the ISE installation, detect automatically if not specified')
    parser.add_argument('--mars-path',
                        help='path to the modified MARS .jar file, the built-in one by default',
                        default=None)
    parser.add_argument('--java-path', metavar='path',
                        default='java', help='path to your jre binary, omit this if java is in your path environment')
    parser.add_argument('--diff-path', metavar='path',
                        default=None,
                        help='path to your diff tool, "diff" for POSIX and "fc" for Windows by default')
    parser.add_argument('--recompile', action='store_true',
                        help='recompile the test bench before running the simulation')
    parser.add_argument('--db', action='store_true',
                        help='specify this to enable delayed branching')
    parser.add_argument('--duration', metavar='time',
                        default=duration_default,
                        help='duration for ISim simulation, "{}" by default'.format(duration_default))
    parser.add_argument('--no-infinite-loop-appendix', action='store_true',
                        help='specify this to prevent an extra infinite loop inserted at the end of simulation, '
                             'where you have to call $finish manually in your project')
    parser.add_argument('--tb-timeout', metavar='secs', type=int,
                        default=None,
                        help='timeout for ISim simulation, {} by default'.format(timeout_default))
    parser.add_argument('--mars-timeout', metavar='secs', type=int,
                        default=None,
                        help='timeout for MARS simulation, {} by default'.format(timeout_default))

    args = parser.parse_args()

    isim = ISim(args.project_path, args.module_name, duration=args.duration,
                appendix=None if args.no_infinite_loop_appendix else INFINITE_LOOP,
                recompile=args.recompile, timeout=args.tb_timeout)
    mars = Mars(args.mars_path, java_path=args.java_path, db=args.db, timeout=args.mars_timeout)
    diff = Diff(args.diff_path)

    judge = MarsJudge(isim, mars, diff)
    judge.all(resolve_paths(args.asm_path))

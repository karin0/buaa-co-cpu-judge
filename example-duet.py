from judge import Mars, ISim, DuetJudge, resolve_paths, INFINITE_LOOP
from judge.utils import CachedList

project_path = 'ise-projects/mips7'
module_name = 'tb'
std_project_path = 'ise-projects/mips7-std'

cases = [
    'cases/interrupts'
]

db = True
duration = 'all'
appendix = INFINITE_LOOP
timeout = 3
recompile = True
skip_passed_cases = True
include_handler = True


isim = ISim(project_path, module_name, duration=duration,
            appendix=appendix, recompile=recompile, timeout=timeout)
std = ISim(std_project_path, module_name, duration=duration,
           appendix=appendix, recompile=recompile, timeout=timeout)
mars = Mars(db=db, timeout=timeout)
judge = DuetJudge(isim, std, mars)


def main():
    with CachedList('passes.json') as passes:
        blocklist = passes if skip_passed_cases else None
        paths = resolve_paths(cases,
                              blocklist=blocklist,
                              on_omit=lambda path: print('Omitting', path),
                              )
        judge.all(paths,
                  self_handler=include_handler,
                  on_success=passes.append,
                  on_error=passes.close_some,
                  )


if __name__ == '__main__':
    main()

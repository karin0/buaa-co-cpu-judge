from judge import Mars, ISim, MarsJudge, resolve_paths, INFINITE_LOOP
from judge.utils import CachedList

project_path = 'ise-projects/mips5'
module_name = 'tb'

db = True
duration = 'all'
appendix = INFINITE_LOOP
timeout = 3
recompile = False
skip_passed_cases = True

cases = [
    'cases/5',
    'cases/extra',
    'cases/case*'
]

isim = ISim(project_path, module_name, duration=duration,
            appendix=appendix, recompile=recompile, timeout=timeout)
mars = Mars(db=db, timeout=timeout)
judge = MarsJudge(isim, mars)


def main():
    passes = CachedList('passes.json')
    with passes:
        blocklist = passes if skip_passed_cases else None
        paths = resolve_paths(cases,
                              blocklist=blocklist,
                              on_omit=lambda path: print('Omitting', path),
                              )
        # judge.load_handler(handler)
        judge.all(paths,
                  on_success=passes.append,
                  on_error=passes.close_some,
                  )


if __name__ == '__main__':
    main()

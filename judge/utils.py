import os, subprocess, glob, threading, json
from hashlib import md5


def try_mkdir(path, func=os.mkdir):
    if not os.path.isdir(path):
        func(path)


class CachedList:
    def __init__(self, fn):
        self.fn = fn
        self.a = []
        self.changed = False
        self.mutex = threading.Lock()
        self.changed_mutex = threading.Lock()

    def __enter__(self):
        try:
            with open(self.fn, encoding='utf-8') as fp:
                self.a = json.load(fp)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self.a = []
        return self.a

    def close(self):
        with self.changed_mutex:
            if self.changed:
                with self.mutex:
                    with open(self.fn, 'w', encoding='utf-8') as fp:
                        json.dump(self.a, fp, ensure_ascii=False, indent=4, separators=(',', ': '))
                    self.changed = False

    def close_some(self, _):
        return self.close()

    def __exit__(self, t, v, tb):
        self.close()

    def __iter__(self):
        return self.a.__iter__()

    def __in__(self, v):
        return v in self.a

    def append(self, v):
        with self.changed_mutex:
            self.changed = True
        with self.mutex:
            return self.a.append(v)


class TmpDir:
    def __init__(self, path):
        self.path = path
        self.created = False

    def __call__(self):
        if not self.created:
            try_mkdir(self.path, func=os.makedirs)
            self.created = True
        return self.path


def hash_file(fn):
    with open(fn, 'rb') as fp:
        return md5(fp.read()).hexdigest()[:10]


def run(cmd, quiet=True):
    if quiet:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(cmd)


def kill_pid(pid):
    if os.name != 'nt':
        raise NotImplementedError
    run(['taskkill', '/f', '/pid', str(pid)])


def kill_im(im):
    if os.name != 'nt':
        raise NotImplementedError
    if not os.path.splitext(im)[1]:
        im += '.exe'
    run(['taskkill', '/f', '/im', im])


def resolve_paths(paths, recursive=True, use_glob=True, blocklist=None, on_omit=None):
    if isinstance(paths, str):
        r = [paths]
    elif use_glob:
        r = []
        for p in paths:
            r += glob.glob(p, recursive=recursive)
    else:
        r = paths

    q = []
    if blocklist:
        ban_set = set(os.path.abspath(path) for path in blocklist)

        def push(path):
            if os.path.abspath(path) in ban_set:
                if on_omit:
                    on_omit(path)
            else:
                q.append(path)
    else:
        push = q.append

    for path in r:
        if recursive and os.path.isdir(path):
            for file_path in glob.glob(os.path.join(path, '**', '*.asm'), recursive=True):
                push(file_path)
        else:
            push(path)

    return q

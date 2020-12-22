import threading


class PropagatingThread(threading.Thread):
    def run(self):
        self.exc = None
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e

    def join(self):
        super(PropagatingThread, self).join()
        if self.exc:
            raise self.exc
        return self.ret


class Atomic:
    Lock = threading.Lock

    def __init__(self, data):
        self.mutex = self.Lock()
        self.data = data

    def __enter__(self):
        self.mutex.__enter__()
        return self.data

    def __exit__(self, t, v, tb):
        return self.mutex.__exit__(t, v, tb)


class RAtomic(Atomic):
    Lock = threading.RLock


class Counter(RAtomic):
    def __init__(self, x=0):
        super().__init__(x)

    def increase(self, x=1):
        with self.mutex:
            self.data += x

    def value(self):
        return self.data

    def __enter__(self):
        self.mutex.__enter__()

    def __str__(self):
        return str(self.data)

    __int__ = value
    __repr__ = __str__

import threading

mutex_context_wrappers = \
    ((lambda self: self.mutex.__enter__()),
     (lambda self, t, v, tb: self.mutex.__exit__(t, v, tb)))


class Set:
    def __init__(self):
        self.data = set()
        self.mutex = threading.RLock()

    def add(self, k):
        with self.mutex:
            self.data.add(k)

    def remove(self, k):
        with self.mutex:
            self.data.remove(k)

    def __contains__(self, k):
        with self.mutex:
            return k in self.data

    __enter__, __exit__ = mutex_context_wrappers


class Counter:
    def __init__(self, x=0):
        self.data = x
        self.mutex = threading.RLock()

    def increase(self, x=1):
        with self.mutex:
            self.data += x

    def value(self):
        return self.data

    def __str__(self):
        return str(self.data)

    __int__ = value
    __repr__ = __str__
    __enter__, __exit__ = mutex_context_wrappers

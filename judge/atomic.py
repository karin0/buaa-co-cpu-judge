import threading


class Set:
    def __init__(self):
        self.data = set()
        self.mutex = threading.Lock()

    def add(self, k):
        with self.mutex:
            self.data.add(k)

    def remove(self, k):
        with self.mutex:
            self.data.remove(k)

    def __contains__(self, k):
        with self.mutex:
            return k in self.data


class Counter:
    def __init__(self, x=0):
        self.data = x
        self.mutex = threading.Lock()

    def increase(self, x=1):
        with self.mutex:
            self.data += x

    def value(self):
        return self.data

    __int__ = value

    def __str__(self):
        return str(self.data)

    __repr__ = __str__

#!/usr/bin/env python3

class iterstream():
    def __init__(self, it):
        self.it = iter(it)
        self.buf = None
        self.mode = 's'

    def read(self, n=None):
        assert n == None or n >= 0

        l = [ self.buf ] if self.buf else []
        llen = len(l[0]) if self.buf else 0

        try:
            while not n or llen < n:
                l += [ next(self.it) ]
                llen += len(l[-1])
                self.mode = 'b' if isinstance(l[-1], bytes) else 's'
                print(l, llen, self.mode)
        except StopIteration:
            pass
        except:
            raise

        if len(l) == 0:
            return '' if self.mode == 's' else b''

        n = n or llen
        n = llen if n > llen else n
        x = l.pop()
        a = n - (llen - len(x))
        l += [ x[:a] ]
        self.buf = x[a:]

        return ''.join(l) if self.mode == 's' else b''.join(l)


#!/usr/bin/env python3

from collections import Iterator,Generator
from subprocess import Popen,PIPE
from sys import stdin, stdout, stderr
from shlex import split
from select import select
from threading import Thread
from io import IOBase

class run():
    def __init__(self, cmd, input=None, ignore_err=False):
        self.ignore_err = ignore_err
        self.p = Popen(split(cmd), stdin=None or PIPE, stdout=PIPE, stderr=PIPE if not ignore_err else None)
        self._out = None
        self._err = None
        self._text = None
        self._err_text = None

        if input:
            self.inpipe = pipe(input, self.p.stdin)
            self.inpipe.start()
        else:
            self.inpipe = None

    @property
    def out(self):
        if not self._out:
            self._out = self.p.stdout.read()

        return self._out

    @property
    def text(self):
        if not self._text:
            self._text = self.out.decode('utf-8')

        return self._text

    @property
    def err(self):
        if not self._err and not self.ignore_err:
            self._err = self.p.stderr.read()

        return self._err

    @property
    def err_text(self):
        if not self._err_text and not self.ignore_err:
            self._err_text = self.err.decode('utf-8')

        return self._err_text

    def iter_text(self, chunk_size=4096):
        return self.iter_out(chunk_size, mode='s')
    
    def iter_out(self, chunk_size=4096, mode='b'):
        assert self._out == None
        return self.iter_stream(self.p.stdout, mode, chunk_size)

    def iter_err(self, chunk_size=4096, mode='b'):
        assert self._err == None
        assert self.ignore_err != None
        return self.iter_stream(self.p.stderr, mode, chunk_size)

    def iter_err_text(self, chunk_size=4096):
        assert self._err_text == None
        return self.iter_err(chunk_size, mode='s')

    def iter_stream(self, s, mode='b', chunk_size=4096):
        assert mode in [ 'b', 's' ]
        b = s.read(chunk_size)
        while b != b'':
            # handle multi-byte Unicode sequence on chunk boundary in string mode
            while s.peek(1) != b'' and s.peek(1)[0] > 0x7f:
                b += s.read(1)

            yield b if mode == 'b' else b.decode('utf-8')
            b = s.read(chunk_size)

    def kill(self):
        self.p.kill()

    @property
    def returncode(self):
        self.p.poll()
        return self.p.returncode


class pipe(Thread):
    def __init__(self, input, output, chunk_size=4096):
        super(pipe, self).__init__()
        self.output = output
        self.chunk_size = chunk_size
        self.input = input

    def run(self):
        i = self.input
        o = self.output

        if isinstance(i, str):
            o.write(i.encode('utf-8'))
        elif isinstance(i, bytes):
            o.write(i)
        elif isinstance(i, IOBase):
            b = i.read(self.chunk_size)
            while b not in [ b'', '' ]:
                o.write(b if isinstance(b, bytes) else b.encode('utf-8'))
                b = i.read(self.chunk_size)
        elif isinstance(i, list) or isinstance(i, Iterator) or isinstance(i, Generator):
            for chunk in i:
                o.write(chunk)

        o.close()


# convert iterables into stream
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



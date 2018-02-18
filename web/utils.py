#!/usr/bin/env python3

from collections import Iterator,Generator
from subprocess import Popen,PIPE,DEVNULL
from sys import stdin, stdout, stderr
from shlex import split
from select import select
from threading import Thread
from io import IOBase
from werkzeug.routing import BaseConverter

class run():
    debug=False

    def __init__(self, cmd, input=None, ignore_err=False):
        debug('run init')
        self.default_buf_size=100*1024
        self.ignore_err = ignore_err
        self.p = Popen(split(cmd), stdin=PIPE if input else None, stdout=PIPE, stderr=None if ignore_err else PIPE)
        self._out = None
        self._err = None
        self._text = None
        self._err_text = None

        if input:
            self.inpipe = pipe(input, self.p.stdin, chunk_size=self.default_buf_size)
            self.inpipe.start()
        else:
            self.inpipe = None

    @property
    def out(self):
        if not self._out:
            self._out = self.p.stdout.read()

        return self._out

    @property
    def stdout(self):
        return self.p.stdout
    
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

    def iter_text(self, chunk_size=None):
        return self.iter_out(chunk_size or self.default_buf_size, mode='s')
    
    def iter_out(self, chunk_size=None, mode='b'):
        assert self._out == None
        return self.iter_stream(self.p.stdout, mode, chunk_size or self.default_buf_size)

    def iter_err(self, chunk_size=None, mode='b'):
        assert self._err == None
        assert self.ignore_err != None
        return self.iter_stream(self.p.stderr, mode, chunk_size or self.default_buf_size)

    def iter_err_text(self, chunk_size=None):
        assert self._err_text == None
        return self.iter_err(chunk_size or self.default_buf_size, mode='s')

    def iter_stream(self, s, mode='b', chunk_size=None):
        debug('run iter_stream start')
        assert mode in [ 'b', 's' ]
        b = s.read(chunk_size or self.default_buf_size)
        while b != b'':
            debug('run iter_stream chunk', len(b))
            # handle multi-byte Unicode sequence on chunk boundary in string mode
            while mode == 's' and s.peek(1) != b'' and s.peek(1)[0] > 0x7f:
                b += s.read(1)

            yield b if mode == 'b' else b.decode('utf-8')
            b = s.read(chunk_size or self.default_buf_size)
        debug('run iter_stream end')

    def kill(self):
        self.p.kill()

    @property
    def returncode(self):
        self.p.poll()
        return self.p.returncode

    def __iter__(self):
        return iter(self.iter_out())

class pipe(Thread):
    def __init__(self, input, output, chunk_size=4096):
        debug('pipe init')
        super(pipe, self).__init__()
        self.output = output
        self.chunk_size = chunk_size
        self.input = input

    def run(self):
        debug('pipe run start')
        i = self.input
        o = self.output

        if isinstance(i, str):
            o.write(i.encode('utf-8'))
        elif isinstance(i, bytes):
            o.write(i)
        elif isinstance(i, IOBase):
            b = i.read(self.chunk_size)
            while b not in [ b'', '' ]:
                debug('pipe run iter() chunk', len(b), flush=True)
                o.write(b if isinstance(b, bytes) else b.encode('utf-8'))
                b = i.read(self.chunk_size)
        elif isinstance(i, list) or isinstance(i, Iterator) or isinstance(i, Generator):
            for chunk in i:
                debug('pipe run list/iterator/generator chunk', len(chunk))
                o.write(chunk)
        else:
            # try to create an iterator *roll-eyes*
            for chunk in iter(i):
                debug('pipe run iter() chunk', len(chunk))
                o.write(chunk)

        o.close()
        debug('pipe run end')


# convert iterables into stream
class iterstream():
    def __init__(self, it):
        self.it = iter(it)
        self.buf = None
        self.mode = 's'
        self.p=0


    def seek(self, i):
        print('Seeking to %d' % i, file=stderr)
        if i < self.p:
            raise Exception('Cannot seek: %d < %d' % (i, self.p))

        while self.p < i:
            b = self.read(min(10*1024, i - self.p))

            if len(b) == 0:
                raise Exception('Cannot seek past end of stream: %d > %d' % (i, self.p))


    def tell(self):
        return self.p


    def read(self, n=None):
        return self._read(n)

    def _read(self, n=None):
        assert n == None or n >= 0

        l = [ self.buf ] if self.buf else []
        llen = len(l[0]) if self.buf else 0

        try:
            while not n or llen < n:
                l += [ next(self.it) ]
                llen += len(l[-1])
                self.mode = 'b' if isinstance(l[-1], bytes) else 's'
                debug(l, llen, self.mode)
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

        self.p += n

        return ''.join(l) if self.mode == 's' else b''.join(l)


def debug(*args, **kwargs):
    if run.debug:
        print('debug:', *args, **kwargs, file=stderr, flush=True)


def create_response(identifier, runstr, mimetype):
    return Response(
            run(
                runstr,
                get(identifier, stream=True).iter_content(100*1024),
                ignore_err=True),
            mimetype=mimetype)

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

mimes = {
			'jp2': 'image/jp2',
			'png': 'image/png',
			'jpg': 'image/jpg',
		    'jpeg': 'image/jpg',
		    'gif': 'image/gif',
		    'tif': 'image/tiff',
		    'tiff': 'image/tiff',
		    'json': 'application/json',
		    'json-ld': 'application/ld+json'
		}


def create_key(url, region='full', scale='max', rotation='0', quality='default', format=None):
    format = format or get_setting('cache_format', 'jpg')
    scale = 'max' if scale == 'full' else scale
    quality = 'default' if quality == 'color' else quality

    return ':'.join((url, region, scale, rotation, quality, format))


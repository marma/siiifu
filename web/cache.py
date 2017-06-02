#!/usr/bin/env python3

from collections import Iterator
from sys import stdin,stdout,stderr
from io import IOBase,TextIOBase
import requests
from json import dump,load
from flask import Flask,Response,request,send_file
from urllib.parse import urlparse
from contextlib import closing
from hashlib import md5
from os.path import exists,basename,dirname
from os import makedirs
from datetime import datetime

class Cache():
    debug = False

    def __init__(self, base):
        self.base=base


    def set(self, key, data, info={}):
        self.pdebug('set: %s' % key)
        try:
            for chunk in self._set(key, data, info):
                pass

            return self.lookup(key)
        except Exception as e:
            try:
                self.delete(key)
            except:
                pass

            raise e


    def iter_set(self, key, data, info={}, chunk_size=100*1024):
        self.pdebug('iter_set %s' % key)
        return self._set(key, data, info, chunk_size)


    def _set(self, key, data, info={}, chunk_size=100*1024):
        if key == '':
            raise Exception('Empty key value')

        fname = self.filename(key)

        # possible race condition, but that's fine
        if not exists(dirname(fname)):
            try:
                makedirs(dirname(fname))
            except:
                pass

        d = dict(info)
        d['mode'] = 'b'
        d['key'] = key
        d['time'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%m:%SZ')

        # should probably lock this section using the key
        with open(fname, mode='wb') as f:
            if isinstance(data, str):
                d['mode'] = 's'
                f.write(data.encode('utf-8'))
                yield data
            elif isinstance(data, bytes):
                f.write(data)
                yield data
            elif isinstance(data, Iterator):
                for b in data:
                    if isinstance(b, str):
                        d['mode'] = 's'
                        be=b.encode('utf-8')
                        f.write(be)
                    else:
                        f.write(b)

                    yield b
            elif isinstance(data, IOBase):
                b=data.read(chunk_size)
                while len(b) != 0:
                    if isinstance(b, str):
                        d['mode'] = 's'
                        be=b.encode('utf-8')
                        f.write(be)
                    else:
                        f.write(b)

                    yield b
            else:
                raise Exception('Unexpected type for data (%s)', str(type(data)))
 
        with open(fname + '.json', mode='w') as f:
            dump(d, f)



    def get(self, key):
        self.pdebug('get %s' % key)

        if key in self:
            fname = self.filename(key)

            with open(fname + '.json') as fh:
                info = load(fh)

                with open(fname, mode='rb' if info['mode'] == 'b' else 'r') as f:
                    return f.read()
        else:
            return None


    def iter_get(self, key, chunk_size=100*1024):
        self.pdebug('iter_get %s' % key)
        fname = self.filename(key)

        if exists(fname + '.json'):
            with open(self.filename(key) + '.json') as fh:
                info = load(fh)

                with open(self.filename(key), mode='rb' if info['mode'] == 'b' else 'r') as f:
                    b=f.read(chunk_size)
                    while len(b) != 0:
                        yield b
                        b=f.read(chunk_size)

    def getfile(self, key):
        if key in self :
            return self.filename(key)
        else:
            return None


    def __contains__(self, key):
        if exists(self.filename(key) + '.json'):
            self.pdebug('LOOKUP HIT: %s' % key)
            return True
        else:
            self.pdebug('LOOKUP MISS: %s' % key)
            return False

    
    def lookup(self, key):
        if key in self:
            with open(self.filename(key) + '.json') as f:
                return load(f)
        else:
            return None

    def delete(self, key):
        fname = self.filename(key)
        
        if exists(fname):
            remove(fname)

        if exists(fname + '.json'):
            remove(fname + '.json')


    def filename(self, key):
        hex = md5(key.encode('utf-8')).hexdigest()

        return '/'.join([ self.base ] + [ hex[ 2*i:2*i+2 ] for i in range(0,4) ] + [ hex ])

    def pdebug(self, *args):
        if self.debug:
            print('CACHE', *args, file=stderr, flush=True)

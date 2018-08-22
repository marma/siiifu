from requests import Session,get,head
from os import SEEK_SET, SEEK_CUR, SEEK_END
from sys import stdin,stderr
from datetime import datetime
from io import RawIOBase,UnsupportedOperation,BufferedReader,TextIOWrapper

# larger than usual buffer size due to GET operation being expensive
DEFAULT_BUFFER_SIZE=10*1024
seek_whence = { SEEK_SET:'SEEK_SET', SEEK_CUR:'SEEK_CUR', SEEK_END:'SEEK_END' }

def open(url, mode='r', auth=None, buffering=-1, encoding=None, headers={}, debug=False):
    binary = mode[-1] == 'b'

    if mode[0] != 'r':
        raise Exception('only read-only streams supported')

    if binary:
        if encoding != None:
            raise ValueError('binary mode doesn\'t take an encoding argument')
    
        if buffering == 1:
            raise ValueError('line buffering not supported in binary mode')

    if not binary and buffering == 0:
        raise ValueError('can\'t have unbuffered text I/O')

    if not isinstance(buffering, int):
        raise TypeError('an integer is required (got type %s)' % type(buffering).__name__)

    raw = HttpIO(url, auth=auth, headers=headers, debug=debug)
    buf = raw

    if buffering != 0:
        buf = BufferedReader(raw, buffer_size=DEFAULT_BUFFER_SIZE if buffering < 2 else buffering)

    return buf if binary else TextIOWrapper(buf, encoding)


class HttpIO(RawIOBase):
    def __init__(self, url, auth=None, debug=False, headers={}):
        self.url = url
        self.auth = auth
        self.debug = debug
        self.headers = headers
        self.position = 0
        self.stream_position = 0
        self.size = None
        self.session = Session()
        self.r = None
        self.etag = None

        self._position()


    def close(self):
        if not self.closed:
            try:
                self.r.close()
                self.session.close()
            finally:
                self.r = None
                super().close()


#    def fileno(self):
#        if self.closed:
#            raise ValueError('I/O operation on closed stream')
#
#        self._log('fileno', self.r.raw.fileno())
#
#        return self.r.raw.fileno()


    def read(self, size=-1):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        self._log('read', size)

        if self.size is not None and self.position > self.size:
            return b''

        # reposition?
        if self.r == None or self.stream_position != self.position:
            self._position()

        r = self.r.raw.read(size)
        self.position += len(r)
        self.stream_position = self.position

        return r


    def readable(self):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True


    def readall(self):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        self._log('readall')

        return self.r.raw.read()


    def readinto(self, b):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        self._log(f'readinto len(b) = {len(b)}')

        # reposition?
        if self.r == None or self.stream_position != self.position:
            self._position()

        n = self.r.raw.readinto(b)
        self.position += n
        self.stream_position = self.position

        return n


    def seek(self, offset, whence=SEEK_SET):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        if whence not in seek_whence.keys():
            raise ValueError(f'whence {whence} not supported')

        if not isinstance(offset, int):
            raise TypeError(f'offset must be int, not {type(offset).__name__}')

        pos = self.position
        if whence == SEEK_SET:
            pos = offset
        elif whence == SEEK_CUR:
            pos += offset
        elif whence == SEEK_END:
            if self.size == None:
                raise UnsupportedOperation('end-relative seek not supported for this URL')

            pos = self.size + offset
        
        if pos < 0:
            raise ValueError(f'resulting offset {pos} < 0')

        self._log(f'seek from {self.position} + ({offset}, {seek_whence[whence]}) -> {pos}')

        self.position = pos

        return self.position


    def seekable(self):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True


    def tell(self):
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        self._log('tell', self.position)

        return self.position


    def writable(self):
        return False


    def _position(self):
        self._log('_position', 'position=%d, stream_position=%d' % (self.position, self.stream_position))

        if self.r:
            self.r.close()

        headers = { 'Accept-Encoding': 'identity'}
        headers.update({ 'Range': 'bytes=%d-' % self.position } if self.position != 0 else {})
        headers.update(self.headers)

        self.r = self.session.get(self.url, auth=self.auth, stream=True, headers=headers)
        
        if self.position != 0 and self.r.status_code != 206:
            raise UnsupportedOperation('could not reposition for this URL')

        if self.position == 0 and 'Content-Length' in self.r.headers:
            self.size = int(self.r.headers['Content-Length'])

        self.accept_ranges = 'bytes' in self.r.headers.get('Accept-Ranges', '')
        self.r.raw.decode_content=True
        self.stream_position = self.position


    def _log(self, mtype, *args):
        if self.debug:
            print(self, datetime.now(), mtype, *args, file=stderr, flush=True)


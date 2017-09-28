from re import match
from urllib import parse
from PIL import Image,ImageFile,ImageFilter
from requests import get
from contextlib import closing
from utils import run,iterstream
from caching import cache
from json import dumps,loads
from flask_api.exceptions import NotFound
from threading import RLock
from io import BytesIO

_lockslock=RLock()
_locks={}
_icache={}

mimes = {
        'jp2': 'image/jp2',
        'png': 'image/png',
        'jpg': 'image/jpg',
        'jpeg': 'image/jpg',
        'gif': 'image/gif',
        'tif': 'image/tiff',
        'tiff': 'image/tiff',
        'json': 'application/json',
        'json-ld': 'application/ld+json' }

def lock(url):
    with _lockslock:
        if not url in _locks:
            _locks[url] = RLock()

        return _locks[url]

def _get_image(url):
    with lock(url):
        if url in _icache:
            print('_icache hit')
            return _icache[url]
        else:
            print('_icache miss')

        req = get(url, stream=True)
        req.raw.decode_stream=True
        r = run('gm convert - -depth 8 tif:-', req.raw, ignore_err=True)
        _icache[url] = Image.open(r.stdout)

        return _icache[url]


# does not work with files that need the whole file read for identification
def get_info(url):
    key = url + '/info.json'

    with lock(url):
        if key in cache:
            return loads(cache.get(key))
        else:
            with closing(get(url, stream=True)) as r:
                b = next(r.iter_content(50*1024))
                p = run('gm identify -' , b, ignore_err=True)
                s = p.text.split()

            if len(s) == 0:
                # get the whole file, which might take some time
                with closing(get(url, stream=True)) as r:
                    p = run('gm identify -' , r.iter_content(100*1024), ignore_err=True)
                    s = p.text.split()

            ret = { 'format': s[1], 'width': s[2].split('x')[0], 'height': s[2].split('x')[1].split('+')[0] }
            cache.set(key, dumps(ret))

            return ret


def get_image(prefix, url, region, scale, rotation, quality, format):
    key = create_key(url, region, scale, rotation, quality, format)
    info = get_info(url)

    with lock(url):
        if key in cache:
            return cache.iter_get(key)
        else:
            return cache.iter_set(
                    key,
                    create_image(
                        _get_image(url),
                        info,
                        prefix,
                        url,
                        region,
                        scale,
                        rotation,
                        quality,
                        format))


def create_image(image, info, prefix, url, region, scale, rotation, quality, format):
    # region
    if region != 'full':
        if region == 'square':
            diff = abs(image.width-image.height)
            if image.width > image.height:
                x,y,w,h = diff/2, 0, image.width - diff/2, image.height
            else:
                x,y,w,h = 0, diff/2, image.width, image.height - diff/2
        elif region[:4] == 'pct:':
            z = [ image.width, image.height, image.width, image.height ]
            s = [ int(z[x[0]]*float(x[1])) for x in enumerate(region[4:].split(',')) ]
            x,y,w,h = s[0], s[1], min(s[2], image.width), min(s[3], image.height)
        else:
            s = [ int(x) for x in region.split(',') ]
            x,y,w,h = s[0], s[1], min(s[2], image.width-s[0]), min(s[3], image.height-s[1])

        print('crop: ', x,y,w,h, flush=True)
        image = image.crop((x,y,x+w,y+h))

    # size
    if scale not in [ 'full', 'max' ]:
        if scale[:4] == 'pct:':
            s = float(scale[4:])/100
            if s <= 1.0:
                w,h = int(image.width*s), int(image.height*s)
        else:
            s = scale.split(',')
            print(s)
            if s[0] == '':
                s[1] = min(int(s[1]), image.width)
                w,h = int(image.width * s[1] / image.height), s[1]
            elif s[1] == '':
                print(s[0], )
                s[0] = min(int(s[0]), image.width)
                w,h = s[0], int(image.height * s[0] / image.width)
            else:
                s = [ min(int(s[0]), image.width), min(int(s[1]), image.height) ]
                w,h = s[0], s[1]
 
        print('resize: ', w,h, flush=True)
        image = image.resize((w,h), resample=Image.LANCZOS)

    # rotation
    if rotation != "0":
        image = image.rotate(float(rotation), expand=1)

    # quality
    if quality not in [ 'default', 'color' ]:
        if quality == 'gray':
            image = image.convert('L')
        elif quality == 'bitonal':
            image = image.convert('1')
        elif quality == 'edge':
            image = image.filter(ImageFilter.FIND_EDGES)

    b = BytesIO()
    icc_profile = image.info.get("icc_profile")
    image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

    return b.getvalue()


def create_key(url, region, scale, rotation, quality, format):
    scale = 'max' if scale == 'full' else scale
    quality = 'default' if quality == 'color' else quality

    return ':'.join((url, region, scale, rotation, quality, format))


from re import match
from urllib import parse
from PIL import Image,ImageFile
from requests import get
from contextlib import closing
from utils import run
from magic import Magic
from caching import cache
from json import dumps,loads
from flask_api.exceptions import NotFound

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

# does not work with files that need the whole file read for identification
def get_info(url):
    key = url + '/info.json'

    if key in cache:
        return loads(cache.get(key))
    else:
        with closing(get(url, stream=True)) as r:
            b = next(r.iter_content(50*1024))
            p = run('gm identify -' , b, ignore_err=True)
            s = p.text.split()

        ret = { 'format': s[1], 'width': s[2].split('x')[0], 'height': s[2].split('x')[1] }
        cache.set(key, dumps(ret))

        return ret


def get_image(prefix, url, region, scale, rotation, quality, format):
    key = create_key(url, region, scale, rotation, quality, format)
    info = get_info(url)

    # implement locking based on original resource

    if key in cache:
        return cache.iter_get(key)
    elif mimes[info['format'].lower()] == mimes[format] and \
            region == 'full' and scale == 'max' and \
            rotation == '0' and quality == 'default':
        with closing(get(url, stream=True)) as r:
            return cache.iter_set(key, r.iter_content(100*1024))
    else:
        return cache.iter_set(
                key,
                create_image(
                    prefix,
                    url,
                    region,
                    scale,
                    rotation,
                    quality,
                    format))
    

def create_image(prefix, url, region, scale, rotation, quality, format):
    key = create_key(url, region, scale, rotation, quality, format)
    
    runstr = 'gm convert - {options} {format}:-'
    options = [ ]

    # region
    if region != 'full':
        if region == 'square':
            options += [ '-set', 'option:size', '%[fx:min(w,h)]x%[fx:min(w,h)]', 'xc:none', '+swap', '-gravity', 'center', '-composite' ]
        elif region[:4] == 'pct:':
            # bug - offsets still in pixels
            s = [ float(x) for x in region.split(',') ]
            assert len(s) == 4
            options += [ '-crop', '%%%fx%f+%f+%f' % (s[2], s[3], s[0], s[1]) ] 
        else:
            s = [ int(x) for x in region.split(',') ]
            assert len(s) == 4
            options += [ '-crop', '%dx%d+%d+%d' % (s[2], s[3], s[0], s[1]) ]
            
    # size
    if scale not in [ 'full', 'max' ]:
        if scale[:4] == 'pct:':
            assert float(scale[4:]) <= 100.0
            options += [ '-resize', scale[4:] + '%' ]
        else:
            s = scale.split(',')
            assert scale != ',' and len(s) == 2
            options += [ '-resize', ('\\!' if s[0] != '' and s[1] != '' else '') + scale.replace(',', 'x') + '\\>' ]

    # rotation
    if rotation != "0":
        # bug - bitonal does not work with transparency
        if format in [ 'png', 'gif' ] and quality != 'bitonal':
            options += [ '-background', 'transparent' ]

        options += [ '-rotate', str(float(rotation)) ]

    # quality
    if quality not in [ 'default', 'color' ]:
        if quality == 'gray':
            options +=  [ '-colorspace', 'gray' ]
        elif quality == 'bitonal':
            options += [ '-threshold', '50%' ]

    runstr = runstr.format(format=format, options=' '.join(options))    
   
    jfkey = create_key(url, 'full', 'max', '0', 'default', 'jpg')
    if jfkey in cache:
        # get full JPEG image from cache
        if key == jfkey:
            yield from cache.iter_get(key)
        else:
            yield from cache.iter_set(
                        key,
                        run(runstr, cache.iter_get(jfkey), ignore_err=True).iter_out(100*1024))
    else:
        # convert, and store, from source
        with closing(get(url)) as r:
            if key == jfkey:
                yield from cache.iter_set(
                            key,
                            run('gm convert - -depth 8 -quality 90 jpg:-',
                                r.iter_content(100*1024),
                                ignore_err=True).iter_out(100*1024))
            else:
                yield from cache.iter_set(
                            key,
                            run(runstr, 
                                cache.iter_set(
                                    jfkey,
                                    run('gm convert - -depth 8 -quality 90 jpg:-',
                                        r.iter_content(100*1024),
                                        ignore_err=True).iter_out(100*1024))).iter_out(100*1024))


def create_key(url, region, scale, rotation, quality, format):
    scale = 'max' if scale == 'full' else scale
    quality = 'default' if quality == 'color' else quality

    return ':'.join((url, region, scale, rotation, quality, format))


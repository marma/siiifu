#!/usr/bin/env python3

from flask import Flask,Response,render_template,request,send_file,make_response,send_from_directory
from os.path import join
from re import match
from urllib import parse
from PIL import Image,ImageFile,ImageFilter
from requests import get
from contextlib import closing
from utils import run,iterstream,create_key
from caching import cache
from json import dumps,loads
from yaml import load
from flask_api.exceptions import NotFound
from threading import RLock
from io import BytesIO
from utils import mimes
from cache import Cache
from math import log2

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
with open(join(app.root_path, 'config.yml')) as f:
    config = load(f)
Cache.debug=True
cache = Cache(**config['cache'])

@app.route('/info')
def info():
    url = request.args['url']

    return Response(
            cache.get(url) if url in cache else dumps(get_info(url), indent=2),
            mimetype='application/json')


@app.route('/image')
def image():
    url = request.args['url']
    region = request.args.get('region', 'full')
    size = request.args.get('size', 'max')
    rotation = request.args.get('rotation', '0')
    quality = request.args.get('quality', 'default')
    format = request.args.get('format', 'jpg')

    if url not in cache:
        save(url)

    # exact match?
    key = create_key(url, region, size, rotation, quality, format)
    if key in cache:
        return Response(cache.iter_get(key), mimetype=mimes[format])

	# image is cached, just not in the right rotation, quality or format?
    key = create_key(url, region, size, '0', 'default', config['settings']['cache_format'])
    if key in cache:
        image = Image.open(BytesIO(cache.get(key)))
    else:
        # image is cached, but size is wrong
        # TODO: use optimal size rather than 'max'
        key = create_key(url, region, 'max', '0', 'default', config['settings']['cache_format'])
        if key in cache:
            image = resize(Image.open(BytesIO(cache.get(key))), size)
        else:
            # requested image is also cropped
            # TODO: use optimal size rather than 'max'
            key = create_key(url, 'full', 'max', '0', 'default', config['settings']['cache_format'])
            if key in cache:
                image = resize(crop(Image.open(BytesIO(cache.get(key))), region), size)
            else:
                raise Exception('Stitching image from tiles not supported yet')

    image = rotate(image, float(rotation))
    image = do_quality(image, quality)

    b = BytesIO()
    icc_profile = image.info.get("icc_profile")
    image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

    return Response(b.getvalue(), mimetype=mimes[format])


def save(url):
    req = get(url, stream=True)
    req.raw.decode_stream=True
    r = run('gm convert - -depth 8 -compress none tif:-', req.raw, ignore_err=True)
    i = Image.open(r.stdout)

    # write info
    info = { 'width': i.width, 'height': i.height, 'format': i.format }
    cache.set(url, dumps(info))

    # save full size?
    if get_setting('cache_full', False):
        save_to_cache(
                create_key(
                    url,
                    'full',
                    'max',
                    '0',
                    'default',
                    get_setting('cache_format', 'jpg')),
                i)

    ingest(i, url)

    return info

def save_to_cache(key, image):
    b = BytesIO()
    icc_profile = image.info.get("icc_profile")
    format = config.get('settings', {}).get('cache_format', 'jpg')
    image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

    cache.set(key, b.getvalue())


def ingest(i, url):
    tile_size = get_setting('tile_size', '512')
    min_n = int(log2(tile_size))
    max_n=int(min(log2(i.width), log2(i.height)))

    for n in reversed(range(min_n, max_n+1)):
        size = 2 ** n

        for x in range(0, int(i.width/size) + 1):
            for y in range(0, int(i.height/size) + 1):
                offset_x = size * x
                offset_y = size * y
                width = min(size, i.width - offset_x)
                height = min(size, i.height - offset_y)

                i2 = i.crop((offset_x, offset_y, offset_x + width-1, offset_y + height-1)) \
                      .resize((int((2**min_n * width)/size), int((2**min_n*height)/size)), Image.LANCZOS)

                if n != min_n:
                    i2 = i2.filter(ImageFilter.UnsharpMask(radius=0.8, percent=90, threshold=3))

                save_to_cache(
                        create_key(
                            url,
                            #','.join( [ str(size*x), str(size*y), str(size*(x+1)-1), str(size*(y+1)-1) ],
                            ','.join([ str(offset_x), str(offset_y), str(offset_x + width-1), str(offset_y + height-1) ]),
                            #'!512,512',
                            ','.join([ str(int((2**min_n * width)/size)), str(int((2**min_n*height)/size)) ]),
                            '0',
                            'default',
                            get_setting('cache_format', 'jpg')),
                        i2)

    for extra in get_setting('prerender', []):
        save_to_cache(
            create_key(url, **extra),
            create_image(url, **extra))


def get_setting(key, default):
    return config.get('settings', {}).get(key, default)


def crop(image, region):
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

        image = image.crop((x,y,x+w,y+h))
   
    return image


def resize(image, scale):
    if scale not in [ 'full', 'max' ]:
        if scale[:4] == 'pct:':
            s = float(scale[4:])/100
            if s <= 1.0:
                w,h = int(image.width*s), int(image.height*s)
        else:
            s = scale.split(',')

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

        return image.resize((w,h), Image.LANCZOS)

    return image


def rotate(image, rotation):
    if rotation != '0':
        image = image.rotate(float(rotation), expand=1)

    return image


def do_quality(image, quality):
    if quality not in [ 'default', 'color' ]:
        if quality == 'gray':
            image = image.convert('L')
        elif quality == 'bitonal':
            image = image.convert('1')
        elif quality == 'edge':
            image = image.filter(ImageFilter.FIND_EDGES)

    return image


def get_info(url):
    with closing(get(url, stream=True)) as r:
        b = next(r.iter_content(50*1024))
        p = run('gm identify -' , b, ignore_err=True)
        s = p.text.split()

    # get the whole file, which might take some time
    if len(s) == 0:
        return save(url)

#        with closing(get(url, stream=True)) as r:
#            p = run('gm identify -' , r.iter_content(100*1024), ignore_err=True)
#            s = p.text.split()
#

    ret = { 'format': s[1], 'width': s[2].split('x')[0], 'height': s[2].split('x')[1].split('+')[0] }

    return ret


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', port=5000, threaded=True)

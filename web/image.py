#!/usr/bin/env python3

from flask import Flask,Response,render_template,request,send_file,make_response,send_from_directory
from os.path import join
from re import match
from urllib import parse
from PIL import Image,ImageFile,ImageFilter
from requests import get
from contextlib import closing
from utils import run,iterstream,create_key
from json import dumps,loads
from yaml import load,FullLoader
from flask_api.exceptions import NotFound
from threading import RLock
from io import BytesIO,UnsupportedOperation
from utils import mimes,run
from cache import Cache
from math import log2
from htfile import open as htopen
from PyPDF2 import PdfFileReader, PdfFileWriter
from pdf2image import convert_from_path, convert_from_bytes
from tempfile import NamedTemporaryFile

Image.MAX_IMAGE_PIXELS = 10000000000

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
with open(join(app.root_path, 'config.yml')) as f:
    config = load(f, Loader=FullLoader)
Cache.debug=False
cache = Cache(**config['cache'])
Image.MAX_IMAGE_PIXELS = 30000*30000

@app.route('/info')
def info():
    url = request.args['url']
    uri = request.args.get('uri', url)

    if uri in cache:
        i = cache.get(uri)
    else:
        with cache.lock(uri + ':worker'):
            # check again after recieving lock
            if uri in cache:
                i = cache.get(uri)
            else:
                i = dumps(get_info(url, uri), indent=2)
                cache.set(uri, i)

    return Response(i, mimetype='application/json')


@app.route('/image')
def get_image():
    url = request.args['url']
    uri = request.args.get('uri', url)
    region = request.args.get('region', 'full')
    size = request.args.get('size', 'max')
    rotation = request.args.get('rotation', '0')
    quality = request.args.get('quality', 'default')
    format = request.args.get('format', 'jpg')
    oversample = request.args.get('oversample', 'false').lower() == 'true'

    i = image_iterator(url, uri, region, size, rotation, quality, format, oversample)

    #print(i, request.args, flush=True)

    return Response(i, mimetype=mimes[format])


def image_iterator(url, uri, region, size, rotation, quality, format, oversample):
    tile_size = get_setting('tile_size', 512)

    # optimistic first attempt at avoiding lookup by fixing size with trailing comma
    if match(r'^\d+,$', size) and match(r'^\d+,\d+,\d+,\d+$', region):
        x,y,w,h = [ int(x) for x in match(r'(\d+),(\d+),(\d+),(\d+)', region).groups() ]
        s = int(match(r'(\d+),', size).group(1))
        size = size + str(int(s*h/w))

    # optimistic attempt at avoiding lookup by fixing max size
    if match(r'^\d+,\d+,\d+,\d+$', region) and match(r'^\d+,\d+$', size):
        x,y,w,h = [ int(x) for x in match(r'(\d+),(\d+),(\d+),(\d+)', region).groups() ]
        sx,sy = [ int(x) for x in match(r'(\d+),(\d+)', size).groups() ]

        if (w,h) == (sx,sy):
            size = 'max'

    # exact match?
    key = create_key(uri, region, size, rotation, quality, format)
    if key in cache:
        yield from cache.iter_get(key)

    if uri in cache:
        i = loads(cache.get(uri))
    else:
        with cache.lock(uri + ':worker'):
            # check again after recieving lock
            if uri in cache:
                i = loads(cache.get(uri))
            else:
                i = save(url, uri=uri)

    # match for normalized key?
    nkey = create_key(uri, region, size, rotation, quality, format, width=i['width'], height=i['height'], tile_size=tile_size, normalize=True)
    if nkey in cache:
        yield from cache.iter_get(nkey)
        return

    # quick hack for JPEG2000 when originals are cached
    if get_setting('opj_decompress') and get_setting('cache_original'):
        okey = uri + ':original'

        if okey not in cache:
            with cache.lock(uri + ':worker'):
                if okey not in cache:
                    # calling get image will cache it
                    get_image(url, uri)
        
        loc = join(*cache.get_location(okey))

        image = opj_decompress(i, loc, region, size, tile_size=tile_size, oversample=oversample)

        image = rotate(image, float(rotation))
        image = do_quality(image, quality)

        b = BytesIO()
        icc_profile = image.info.get("icc_profile")
        image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

        # this can get expensive!
        if get_setting('cache_all', False):
            print('warning: caching arbitrary sized image (%s)' % nkey, flush=True)
            save_to_cache(nkey, image)

        yield b.getvalue()

        return

    # image is cached, just not in the right rotation, quality or format?
    print('doing actual work for uri: ' + uri, flush=True)
    key = create_key(uri, region, size, '0', 'default', config['settings']['cache_format'])
    if key in cache:
        image = Image.open(BytesIO(cache.get(key)))
    else:
        # image is cached, but size is wrong?
        # TODO: use optimal size rather than 'max'
        key = create_key(uri, region, 'max', '0', 'default', config['settings']['cache_format'])
        if key in cache:
            image = resize(Image.open(BytesIO(cache.get(key))), size)
        else:
            # requested image is also cropped
            # TODO: use optimal size rather than 'max'
            key = create_key(uri, 'full', 'max', '0', 'default', config['settings']['cache_format'])
            if key in cache:
                image = Image.open(BytesIO(cache.get(key)))
                image = crop(image, region)
                image = resize(image, size)
            else:
                raise Exception('Stitching image from tiles not supported yet')

    image = rotate(image, float(rotation))
    image = do_quality(image, quality)

    b = BytesIO()
    icc_profile = image.info.get("icc_profile")
    image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

    # this can get expensive!
    if get_setting('cache_all', False):
        print('warning: caching arbitrary sized image (%s)' % nkey, flush=True)
        save_to_cache(nkey, image)

    yield b.getvalue()


def save(url, uri=None):
    uri = uri or url

    i = get_image(url, uri)

    # quick hack to avoid tiling of JPEG2000 images when cached
    if get_setting('cache_original', False) and get_setting('opj_decompress', None) and i.format == 'JPEG2000':
        # do nothing for now
        ...
    else:
        # save full size?
        if get_setting('cache_full', False) and not get_setting('save_original', False):
            save_to_cache(
                    create_key(
                        uri,
                        'full',
                        'max',
                        '0',
                        'default',
                        get_setting('cache_format', 'jpg')),
                    i)

        ingest(i, url, uri)

    # write info
    info = { 'width': i.width, 'height': i.height, 'format': i.format }
    cache.set(uri, dumps(info))

    return info


def get_credentials(url):
    for c in config.get('credentials', {}):
        if match(c['pattern'], url):
            return (c['user'], c['pass'])
    
    return None


def hget(url, stream=False, auth=None):
    return get(url, stream=stream, auth=get_credentials(url))


def get_image(url, uri=None):
    uri = uri or url
    m = match(r'(^.*\.pdf):(\d+)$', url)

    # PDF?
    if m:
        try:
            # TODO: use credentials in config
            r = htopen(m.group(1), mode='rb', auth=get_credentials(url))
            pr = PdfFileReader(r)

            if pr.isEncrypted:
                pr.decrypt('')

            p = pr.getPage(int(m.group(2)))
            pw = PdfFileWriter()
            pw.addPage(p)
            b = BytesIO()
            pw.write(b)
            b.seek(0)
            i = convert_from_bytes(b.read())[0]
        except (UnsupportedOperation,NotImplementedError) as e:
            # download whole file
            r  = htopen(m.group(1), mode='rb', auth=get_credentials(url))
            i = convert_from_bytes(r.read(), 300, first_page=int(m.group(2)), last_page=int(m.group(2)), userpw='')[0]
        except:
            raise
    else:
        print(url, flush=True)
        req = hget(url, stream=True)
        req.raw.decode_stream=True

        if get_setting('cache_original', False):
            print(f'caching original ({uri})', flush=True)
            key = uri + ':original'
            cache.set(key, req.raw)
            i = Image.open(join(*cache.get_location(key)))
        else:
            b = req.raw.read()
            i = Image.open(BytesIO(b))

    return i


def save_to_cache(key, image):
    print('save_to_cache', key, image, flush=True)
    b = BytesIO()
    icc_profile = image.info.get("icc_profile")
    format = config.get('settings', {}).get('cache_format', 'jpg')
    image.save(b, quality=90, icc_profile=icc_profile, progressive=True, format='jpeg' if format == 'jpg' else format)

    cache.set(key, b.getvalue())


def ingest(i, url, uri=None):
    tile_size = get_setting('tile_size', '512')
    min_n = int(log2(tile_size))
    max_n=int(min(log2(i.width), log2(i.height)))
    uri = uri or url

    for n in reversed(range(min_n, max_n+1)):
        size = 2 ** n

        for x in range(0, int((i.width-1)/size) + 1):
            for y in range(0, int((i.height-1)/size) + 1):
                offset_x = size * x
                offset_y = size * y
                width = min(size, i.width - offset_x)
                height = min(size, i.height - offset_y)

                i2 = i.crop((offset_x, offset_y, offset_x + width, offset_y + height)) \
                      .resize((round((2**min_n * width)/size), round((2**min_n*height)/size)), Image.LANCZOS)

                if n != min_n:
                    i2 = i2.filter(ImageFilter.UnsharpMask(radius=0.8, percent=90, threshold=3))

                save_to_cache(
                    create_key(
                        uri,
                        #','.join( [ str(size*x), str(size*y), str(size*(x+1)-1), str(size*(y+1)-1) ],
                        ','.join([ str(offset_x), str(offset_y), str(width), str(height) ]),
                        #'!512,512',
                        ','.join([ str(round((2**min_n * width)/size)), str(round((2**min_n*height)/size)) ]),
                        '0',
                        'default',
                        get_setting('cache_format', 'jpg'),
                        width=i.width,
                        height=i.height,
                        normalize=True),
                    i2)

    for extra in get_setting('prerender', []):
        save_to_cache(
            create_key(uri, **extra),
            create_image(i, **extra))


def get_setting(key, default=None):
    return config.get('settings', {}).get(key, default)


def crop(image, region):
    if region != 'full':
        if region == 'square':
            diff = abs(image.width-image.height)
            if image.width > image.height:
                x,y,w,h = diff/2, 0, image.height, image.height
            else:
                x,y,w,h = 0, diff/2, image.width, image.width
        elif region[:4] == 'pct:':
            z = [ image.width, image.height, image.width, image.height ]
            s = [ int(z[x[0]]*float(x[1])) for x in enumerate(region[4:].split(',')) ]
            x,y,w,h = s[0], s[1], min(s[2], image.width), min(s[3], image.height)
        else:
            s = [ int(x) for x in region.split(',') ]
            x,y,w,h = s[0], s[1], min(s[2], image.width-s[0]), min(s[3], image.height-s[1])

        image = image.crop((x,y,x+w,y+h))
   
    return image


def resize(image, scale, tile_size=None):
    if scale not in [ 'full', 'max' ]:
        max_resize = int(get_setting('max_resize', '20000'))

        if scale[:4] == 'pct:':
            s = float(scale[4:])/100
            if s <= 1.0:
                w,h = int(image.width*s), int(image.height*s)
        elif scale[0] == '!':
            s = scale[1:].split(',')

            if s[0] == '':
                s[1] = min(int(s[1]), image.width)
                w,h = int(image.width * s[1] / image.height), s[1]
            elif s[1] == '':
                s[0] = min(int(s[0]), image.width)
                w,h = s[0], int(image.height * s[0] / image.width)
            else:
                s = [ min(int(s[0]), image.width), min(int(s[1]), image.height) ]
                w,h = s[0], s[1]

            if image.width > image.height:
                h = int(w * image.height / image.width)
            else:
                w = int(h * image.width / image.height)
        else:
            s = scale.split(',')

            if s[0] == '':
                s[1] = int(s[1])
                w,h = int(image.width * s[1] / image.height), s[1]
            elif s[1] == '':
                s[0] = int(s[0])
                w,h = s[0], int(image.height * s[0] / image.width)

                # correct for rounding errors?
                h1 = int(image.height * (s[0]-1) / image.width)
                if tile_size and h > tile_size and h1 <= tile_size:
                    h = tile_size
            else:
                #s = [ min(int(s[0]), image.width), min(int(s[1]), image.height) ]
                w,h = int(s[0]), int(s[1])

        ow = image.width
        image = image.resize((min(w, max_resize), min(h, max_resize)), Image.LANCZOS)

        # sharpen?
        if w / ow < 0.75:
            image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=90, threshold=3))

        return image

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


def get_info(url, uri=None):
    try:
        # attempt to peek information from first 50k of image
        with closing(hget(url, stream=True)) as r:
            r.raw.decode = True
            b = r.raw.read(50*1024)
            i = Image.open(BytesIO(b))

            return { 'format': i.format, 'width': i.width, 'height': i.height }
    except:
        # get the whole file, which might take some time
        return save(url, uri=uri)


def crop_coords(info, region):
    width = info['width']
    height = info['height']

    if region != 'full':
        if region == 'square':
            diff = abs(width - height)
            if width > height:
                x,y,w,h = diff/2, 0, height, height
            else:
                x,y,w,h = 0, diff/2, width, width
        elif region[:4] == 'pct:':
            z = [ width, height, width, height ]
            s = [ int(z[x[0]]*float(x[1])) for x in enumerate(region[4:].split(',')) ]
            x,y,w,h = s[0], s[1], min(s[2], width), min(s[3], height)
        else:
            s = [ int(x) for x in region.split(',') ]
            x,y,w,h = s[0], s[1], min(s[2], width-s[0]), min(s[3], height-s[1])

        return (x,y,w,h)
    else:
        return (0,0,width, height)


def resize_coords(info, scale, tile_size=None):
    width = info['width']
    height = info['height']

    if scale not in [ 'full', 'max' ]:
        max_resize = int(get_setting('max_resize', '20000'))

        if scale[:4] == 'pct:':
            s = float(scale[4:])/100
            if s <= 1.0:
                w,h = int(width*s), int(height*s)
        elif scale[0] == '!':
            s = scale[1:].split(',')

            if s[0] == '':
                s[1] = min(int(s[1]), width)
                w,h = int(width * s[1] / height), s[1]
            elif s[1] == '':
                s[0] = min(int(s[0]), width)
                w,h = s[0], int(height * s[0] / width)
            else:
                s = [ min(int(s[0]), width), min(int(s[1]), height) ]
                w,h = s[0], s[1]

            if width > height:
                h = int(w * height / width)
            else:
                w = int(h * width / height)
        else:
            s = scale.split(',')

            if s[0] == '':
                s[1] = int(s[1])
                w,h = int(width * s[1] / height), s[1]
            elif s[1] == '':
                s[0] = int(s[0])
                w,h = s[0], int(height * s[0] / width)

                # correct for rounding errors?
                h1 = int(height * (s[0]-1) / width)
                if tile_size and h > tile_size and h1 <= tile_size:
                    h = tile_size
            else:
                #s = [ min(int(s[0]), image.width), min(int(s[1]), image.height) ]
                w,h = int(s[0]), int(s[1])

        return (w,h)

    return (width, height)


def opj_decompress(info, loc, region, size, tile_size=None, oversample=False):
    opj_command = get_setting('opj_decompress')

    # crop
    x,y,w,h = crop_coords(info, region)

    # resize
    sw,sy = resize_coords({ 'width': w, 'height': h }, size, tile_size)

    # ignore non-proportional scaling for now
    reduce_factor = int(log2(w/sw))

    # Use larger image to get better quality?
    if oversample:
        reduce_factor = max(0, reduce_factor-1)

    # run opj_decompress
    with NamedTemporaryFile(suffix='.tif') as t:
        cmd = f'{opj_command} -r {reduce_factor} -d {x},{y},{x+w},{y+h} -i {loc} -OutFor TIF -o {t.name}'
        print(cmd, flush=True)

        msg = run(f'{opj_command} -r {reduce_factor} -d {x},{y},{x+w},{y+h} -i {loc} -OutFor TIF -o {t.name}').err
        #print(msg, flush=True)

        t.seek(0)

        b = t.read()

        b = BytesIO(b)

        im = Image.open(b)

    ow = im.width
    im = im.resize((sw,sy), resample=Image.LANCZOS)

    print(ow, flush=True)

    # sharpen?
    if sw / ow < 0.75:
        im = im.filter(ImageFilter.UnsharpMask(radius=0.8, percent=90, threshold=3))

    return im

if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', port=5000, threaded=True)


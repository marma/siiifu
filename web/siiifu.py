#!/usr/bin/env python3

from flask import Flask,Response,render_template,request,send_file,make_response,send_from_directory
from flask_api.exceptions import APIException
from yaml import load
from json import loads
from data import validate,resolve
from utils import RegexConverter,mimes,create_key
from cache import Cache
from urllib.parse import quote
from os.path import join
from requests import get

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.url_map.converters['regex'] = RegexConverter
with open(join(app.root_path, 'config.yml')) as f:
    config = load(f)
Cache.debug=True
cache = Cache(**config['cache'])

# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/info.json')
def info(prefix, identifier):
    p = config['prefixes'][prefix]
    url = resolve(p, identifier)

    if url in cache:
        return send(*cache.get_location(key), 'application/json')
    

@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<regex("default|color|gray|bitonal|edge"):quality>.<regex("jpg|jp2|png"):format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    p = config['prefixes'][prefix]
    url = resolve(p, identifier)
    validate(p, url, region, size, rotation, quality, format)
    key = create_key(url, region, size, rotation, quality, format)
    params = {  'url': url,
                'region': region,
                'size': size,
                'rotation': rotation,
                'quality': quality,
                'format': format }

    headers = { 'Content-Type': mimes[format],
                'Access-Control-Allow-Origin': '*' }

    if key in cache:
        return send(*cache.get_location(key), mimes[format])

    # look for cached image by normalizing parameters
    i = cache.get(url)
    if i:
        i = loads(i)
        nkey = create_key(url, region, size, rotation, quality, format, i['width'], i['height'], normalize=True)

        if nkey != key and nkey in cache:
            return send(*cache.get_location(nkey), mimes[format])

        # since the image is cached, get the image from a worker without locking
        r = get(config['workers']['url'] + 'image', params=params, stream=True)

        return Response(r.iter_content(100*1024), headers=headers)

    with cache.lock(url + ':global'):
        # check cache twice to avoid locking at all in the
        # most common case while still avoiding resource stampede
        if key in cache:
            return send(*cache.get_location(key), mimes[format])

        # unclear if this returns lazily, which will release the lock
        r = get(config['workers']['url'] + 'image', params=params, stream=True)
        return Response(r.iter_content(100*1024), headers=headers)


def send(dir, filename, mime_type):
    r = make_response(send_from_directory(dir, filename))
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Content-Type'] = mime_type

    return r


@app.route('/static/<path:f>')
def static_file(f):
    return send('static', f)


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', port=5000, threaded=True)


#!/usr/bin/env python3

from flask import Flask,Response,render_template,request,send_file,make_response,send_from_directory
from flask_api.exceptions import APIException
from yaml import load
from image import get_image,get_info,mimes
from data import validate,resolve
from utils import RegexConverter
from cache import Cache
from urllib.parse import quote

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.url_map.converters['regex'] = RegexConverter
with open('config.yml') as f:
    config = load(f)
Cache.debug=True

# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/info.json')
def info_json(prefix, identifier):
    p = config['prefixes'][prefix]
    url = resolve(p, identifier)

    r = Response(
            render_template(
                'info.json',
                id=request.scheme + '://' + request.host + '/' + prefix + '/' + quote(identifier, safe=''),
                info=get_info(url)),
            mimetype='application/ld+json')

    r.headers['Access-Control-Allow-Origin'] = '*'

    return r


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<regex("default|color|gray|bitonal|edge"):quality>.<regex("jpg|jp2|png|gif|tif"):format>')
#@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<quality>.<format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    print(prefix, identifier, region, size, rotation, quality, format, flush=True)
    prefix = config['prefixes'][prefix]
    url = resolve(prefix, identifier)
    validate(prefix, url, region, size, rotation, quality, format)

    return Response(
            get_image(
                prefix,
                url,
                region,
                size,
                rotation,
                quality,
                format),
            mimetype=mimes[format])


# Manifest creation
@app.route('/<prefix>/<path:identifier>/manifest')
def manifest(prefix, identifier):
    p = config['prefixes'][prefix]
    url = resolve(p, identifier)

    r = make_response(
            render_template(
                'manifest_single.json',
                url=url,
                url_quoted=quote(url, safe='')))

    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Content-Type'] = 'application/json'

    return r

@app.route('/<prefix>/static/<path:f>')
def static_file(prefix, f):
    r = make_response(send_from_directory('static/', f))
    r.headers['Access-Control-Allow-Origin'] = '*'

    return r


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', port=5000, threaded=True)


#!/usr/bin/env python3

from flask import Flask,Response,render_template,request
from flask_api.exceptions import APIException
from yaml import load
from data import validate,require,info,mimes,resolve
from utils import RegexConverter

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.url_map.converters['regex'] = RegexConverter
with open('config.yml') as f:
    config = load(f)


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/info.json')
def info_json(prefix, identifier):
    prefix = config['prefixes'][prefix]
    url = resolve(prefix, identifier)
    
    return Response(
            render_template(
                'info.json',
                id='/'.join(request.url.split('/')[:-1]),
                info=info(url)),
            mimetype='application/ld+json')


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<quality>.<regex("^((?!json).*)$"):format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    print(prefix, identifier, region, size, rotation, quality, format)
    prefix = config['prefixes'][prefix]
    url = resolve(prefix, identifier)
    validate(prefix, url, region, size, rotation, quality, format)

    return Response(
            require(
                url,
                region,
                size,
                rotation,
                quality,
                format,
                params=request.args),
            mimetype=mimes[format])


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', threaded=True)


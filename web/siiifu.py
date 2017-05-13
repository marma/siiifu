#!/usr/bin/env python3

from sys import stdin,stdout,stderr
from requests import get
from flask import Flask,Response
from yaml import load
from utils import trun
from urllib.parse import urlparse

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
config = load('config.yml')
mimes = { 'jp2': 'image/jp2', 'png': 'image/png', 'jpg': 'image/jpg', 'gif': 'image/gif' }


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<quality>.<format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    print(' / '.join([ prefix, identifier, region, size, str(rotation), quality, format ]), flush=True)

    assert format in [ 'jpg', 'png', 'jp2', 'tif', 'gif' ]
    
    runstr = 'convert {options} - {format}:-'
    options = [ ]

    # check url
    assert urlparse(identifier).scheme in [ 'http', 'https' ]

    # short curcuit?
    if region == 'full' and size in [ 'full', 'max' ] \
       and rotation == 0 and quality == 'default' \
       and identifier.split('.')[-1] == format:
           #runstr = 'cat'
           pass

    # region
    if region != 'full':
       pass 

    # size
    if size not in [ 'full', 'max' ]:
        if size[:4] == 'pct:':
            assert float(size[4:]) <= 100.0
            options += [ '-resize', size[4:] + '%' ]
        else:
            assert size != ',' and len(size.split(',')) == 2
            options += [ '-resize', '\!' + size.replace(',', 'x') + '\>' ]

    # rotation
    if rotation != 0:
        pass

    # quality
    if quality != 'default':
        pass

    print(runstr.format(format=format, options=' '.join(options)), flush=True)

    return Response(
              #trun('cat', identifier),
              trun(runstr.format(format=format, options=' '.join(options)),
                   identifier),
              mimetype=mimes[format])


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/info.json')
def json(prefix, identifier):
    return ' / '.join([ str(prefix), identifier ])


# IIIF AV draft


# Manifest creation
@app.route('/<prefix>/<path:identifier>/manifest')
def manifest(prefix, identifier):
    pass


# Document paging
@app.route('/<prefix>/<path:identifier>/page/<int:n>')
def page(prefix, identifier, page):
    p = config['prefixes'][prefix]

    # get document
    (stream, headers) = get(p['prefix'] + identifier + p['suffix'])


# Get resource
def get(uri):
    pass


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', threaded=True)


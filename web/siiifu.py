#!/usr/bin/env python3

from sys import stdin,stdout,stderr
from requests import get
from flask import Flask,Response
from yaml import load
from utils import run
from urllib.parse import urlparse
from contextlib import closing

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
config = load('config.yml')
mimes = { 'jp2': 'image/jp2', 'png': 'image/png', 'jpg': 'image/jpg', 'gif': 'image/gif' }

def create_response(identifier, runstr, mimetype):
    return Response(run(runstr, get(identifier, stream=True).iter_content(100*1024), ignore_err=True), mimetype=mimetype)


# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/<region>/<size>/<rotation>/<quality>.<format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    print(' / '.join([ prefix, identifier, region, size, rotation, quality, format ]), flush=True)

    assert format in [ 'jpg', 'png', 'jp2', 'tif', 'gif' ]
    
    runstr = 'convert - {options} {format}:-'
    options = [ ]

    # check url
    assert urlparse(identifier).scheme in [ 'http', 'https' ]

    # short curcuit?
    if region == 'full' and size in [ 'full', 'max' ] \
       and rotation == "0" and quality == 'default' \
       and identifier.split('.')[-1] == format:
           #runstr = 'cat'
           pass

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
    if size not in [ 'full', 'max' ]:
        if size[:4] == 'pct:':
            assert float(size[4:]) <= 100.0
            options += [ '-resize', size[4:] + '%' ]
        else:
            s = size.split(',')
            assert size != ',' and len(s) == 2
            options += [ '-resize', ('\\!' if s[0] != '' and s[1] != '' else '') + size.replace(',', 'x') + '\\>' ]

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

    print(runstr, flush=True)

    return create_response(identifier, runstr, mimetype=mimes[format])


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


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', threaded=True)


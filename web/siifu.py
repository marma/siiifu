#!/usr/bin/env python3

from flask import Flask
from yaml import load

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
config = load('config.yml')

# IIIF Image 2.1
@app.route('/<prefix>/<path:identifier>/<region>/<size>/<float:rotation>/<quality>.<format>')
def image(prefix, identifier, region, size, rotation, quality, format):
    assert format in [ 'jpg', 'png', 'jp2' ]
    return ' / '.join([ str(prefix), identifier, region, size, str(rotation), quality, format ])


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

    # 


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', threaded=True)


#!/usr/bin/env python3

from sys import stdin,stdout,stderr
import requests
import json
from flask import Flask,Response,request,send_file
from yaml import load,dump
from urllib.parse import urlparse
from contextlib import closing
from hashlib import md5
from os.path import exists,basename,dirname
from os import makedirs

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

with open('config.yml') as f:
    config=load(f)

# GET
@app.route('/get')
def get():
    url = request.args['url']
    info = lookup(key)

    if info:
        return send_file(info['filename'], mimetype=info['Content-Type'])
    else:
        try:
            r = requests.get(url, stream=True)
            headers = { k: v for (k, v) in r.headers.items() if k in [ 'Content-Type' ] }

            if r.status_code == 200:
                return Response(iter_save(r.iter_content(100*1024), url, headers=headers), headers=headers)
            else:
                return 'Server returned %d for \'%s\'' % (r.status_code, url), 404
        except Exception as e:
            #delete(key)
            raise e


@app.route('/head')
def head():
    url = request.args['url']
    info = lookup(url)

    if info:
        return info
    else:
        return 'Not found', 404

# Push data to cache
@app.route('/cache', methods=[ 'POST' ])
def cache():
    url = request.args['url']
    content_type = request.args['content_type']

    try:
        pass
    except Exception as e:
        raise e

    return 'OK'


def iter_save(input, url, headers={}):
    url = filename(url)
    dir = dirname(fname)

    try:
        # possible race condition
        if not exists(dir):
            makedirs(dir)
    except:
        pass

    with open(fname + '.json', 'w') as out:
        d = dict(headers)
        d['url'] = url
        out.write(json.dumps(d))

    with open(fname, mode='wb') as out:
        for chunk in input:
            out.write(chunk)
            yield chunk


def lookup(key):
    fname = filename(key)

    if exists(fname):
        with open(fname + '.json') as f:
            ret = json.load(f)
        
        ret['filename'] = fname

        return ret
    else:
        return None


def filename(key):
    base = config['cache']['base']
    hex = md5(key.encode('utf-8')).hexdigest()

    return '/'.join([ base ] + [ hex[ 2*i:2*i+2 ] for i in range(0,4) ] + [ hex ])


if __name__ == '__main__':
    app.debug=True
    app.run(host='0.0.0.0', threaded=True)


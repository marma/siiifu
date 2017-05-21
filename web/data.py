from re import match
from urllib import parse
from PIL import Image,ImageFile
from requests import get
from contextlib import closing
from utils import run
from magic import Magic
from config import cache

mimes = { 'jp2': 'image/jp2', 'png': 'image/png', 'jpg': 'image/jpg', 'gif': 'image/gif', 'json': 'application/json', 'json-ld': 'application/ld+json' }

# does not work with files that need the whole file read for identification
def info(url):
    with closing(get(url, stream=True)) as r:
        b = next(r.iter_content(50*1024))
        p = run('identify -' , b, ignore_err=True)
        print(p.text)

        s = p.text.split()

        return { 'format': s[1], 'width': s[2].split('x')[0], 'height': s[2].split('x')[1] }


def acquire(prefix, url, region, scale, rotation, quality, format):
    ret = 

def validate(prefix, url, region, scale, rotation, quality, format):
    scheme = parse.urlsplit(url).scheme
    if scheme not in prefix.get('allowed_schemas', []):
        raise Exception('Scheme \'%s\' not supported' % scheme, 400)

    region_re='full|square|pct:{f},{f},{f},{f}|{d},{d},{d},{d}'.format(f='\\d+(\\.\\d+)?', d='\\d+')
    if not match(region_re, region):
        raise Exception('%s not a valid region' % region, 400)
    
    scale_match=match('(full)|(max)|(\\d+)?,(\\d+)?', scale)
    if not scale_match or scale_match[0] == ',':
        raise Exception('%s not a valid scale' % scale, 400)

    try:
        float(rotation)
    except:
        raise Exception('%s is not a valid value for rotation', 400)

    if quality not in [ 'default', 'color', 'gray', 'bitonal' ]:
        raise Exception('%s not a valid quality' % quality, 400)

    if format not in prefix.get('supported_formats', []):
        raise Exception('Format \'%s\' not supported' % format, 400)

    return True


def resolve(prefix, identifier):
    return prefix['identifier_prefix'] + identifier + prefix['identifier_postfix']


from re import match
from urllib import parse

def validate(prefix, url, region, scale, rotation, quality, format):
    scheme = parse.urlsplit(url).scheme

    if scheme not in prefix.get('allowed_schemas', [ 'http', 'https' ]):
        raise Exception('Scheme \'%s\' not supported' % scheme, 400)

    region_re='^(full|square|pct:{f},{f},{f},{f}|{d},{d},{d},{d})$'.format(f='\\d+(\\.\\d+)?', d='\\d+')
    if not match(region_re, region):
        raise Exception('%s not a valid region' % region, 400)
    
    scale_match=match('^(full|max|{d}*,{d}*|!{d}*,{d}*|pct:{f})$'.format(d='\\d', f='\\d+(\\.\\d+)?'), scale)
    if not scale_match or scale_match.group(1) == ',':
        raise Exception('%s not a valid scale' % scale, 400)

    try:
        float(rotation)
    except:
        raise Exception('%s is not a valid value for rotation', 400)

    if quality not in [ 'default', 'color', 'gray', 'bitonal', 'edge' ]:
        raise Exception('%s not a valid quality' % quality, 400)

    if format not in prefix.get('supported_formats', [ 'jpg' ]):
        raise Exception('Format \'%s\' not supported' % format, 400)

    return True


def resolve(prefix, identifier):
    return prefix['identifier_prefix'] + identifier + prefix['identifier_postfix']


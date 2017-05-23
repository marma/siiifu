from yaml import load
from cache import Cache

with open('config.yml') as f:
    config = load(f)

cache = Cache(config['cache']['base'])



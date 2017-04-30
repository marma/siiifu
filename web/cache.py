from requests import get

class Cache(object):
    def __init__(self):
        pass

    def get(url, params={}, auth={}, headers={}):
        return get(url, params=params, auth=auth, headers=headers)



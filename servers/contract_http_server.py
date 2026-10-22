"""New reference implementation: host/path denotes an HTTPS route, never a file.

Only flat {host, path} and nested {request: {host, path}} requests are supported.
This is a new experimental adapter, not the original benchmark's missing server.
"""
import re
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def resolve_request(arguments):
    if not isinstance(arguments, dict):
        raise ValueError('Arguments must be an object')
    if set(arguments) == {'request'}:
        request = arguments['request']
    else:
        request = arguments
    if not isinstance(request, dict) or set(request) != {'host', 'path'}:
        raise ValueError('Expected exactly host/path, optionally wrapped in request')
    host, route = request['host'], request['path']
    if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
        raise ValueError('Expected a DNS hostname without userinfo, port or scheme')
    if not isinstance(route, str) or not route.startswith('/') or route.startswith('//'):
        raise ValueError('Expected an absolute HTTP route')
    if '\\' in route or any(ord(c) < 32 or ord(c) == 127 for c in route):
        raise ValueError('Invalid route characters')
    parsed = urlsplit(route)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError('Route must not replace the origin or include a fragment')
    url = urlunsplit(('https', host.lower(), parsed.path, parsed.query, ''))
    if urlsplit(url).hostname != host.lower():
        raise ValueError('Origin mismatch')
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_request(arguments):
    url = resolve_request(arguments)
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(urllib.request.Request(url, method='GET'), timeout=15) as response:
        return response.read(4000).decode('utf-8', errors='replace')


_ROUTE_OBJECT = {
    'type': 'object',
    'properties': {'host': {'type': 'string'}, 'path': {'type': 'string'}},
    'required': ['host', 'path'],
    'additionalProperties': False,
}
INPUT_SCHEMA = {
    'type': 'object',
    'oneOf': [
        _ROUTE_OBJECT,
        {'type': 'object', 'properties': {'request': _ROUTE_OBJECT},
         'required': ['request'], 'additionalProperties': False},
    ],
}

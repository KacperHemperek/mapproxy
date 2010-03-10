# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from urlparse import urlparse
from mapproxy.core.response import Response

import logging
log = logging.getLogger(__name__)


class _None(object):
    """
    Accept empty referrers.
    """
    def __call__(self, referrer, _environ):
        return referrer is None

NONE = _None()

class _Blocked(object):
    """
    Accept referrers that were blocked by proxies (XXX, xxx or *****, etc.)
    """
    blocked = re.compile('^[xX*]+$')
    def __call__(self, referrer, _environ):
        if referrer is None:
            return False
        return self.blocked.match(referrer)

BLOCKED = _Blocked()

class _Self(object):
    """
    Accept referrers that are part of the request url.
    http://localhost/foo/ for http://localhost/foo/bar.png
    """
    def __call__(self, referrer, environ):
        if referrer is None:
            return False
        scheme, netloc, path, _params, _query, _fragment = urlparse(referrer)
        if scheme != environ['wsgi.url_scheme']: return False
        if netloc != environ['HTTP_HOST']:
            if _split_netloc(netloc, scheme) != _split_netloc(environ['HTTP_HOST'], scheme):
                return False
        return True

SELF = _Self()

def _split_netloc(netloc, scheme):
    if ':' in netloc:
        return tuple(netloc.split(':'))
    else:
        return netloc, {'http': '80', 'https': '443'}.get(scheme, None)


class _Regex(object):
    def __init__(self, regex):
        self.regex_str = regex
        self.regex = re.compile(regex)
    def __call__(self, referrer, _environ):
        if referrer is None:
            return False
        return self.regex.match(referrer)
    def __repr__(self):
        return 'REGEX(%s)' % self.regex_str

REGEX = _Regex

class ReferrerFilter(object):
    def __init__(self, app, referrers=None):
        self.app = app
        if referrers is None:
            referrers = []
        self.referrers = referrers
    
    def check_referrer(self, environ):
        referrer = environ.get('HTTP_REFERER', None)
        for test in self.referrers:
            if isinstance(test, basestring):
                if referrer.startswith(test):
                    return True
            elif callable(test):
                if test(referrer, environ):
                    return True
        return False
    
    def restricted_response(self, environ, start_response):
        resp = Response('get out of here', status=404)
        return resp(environ, start_response)
    
    def __call__(self, environ, start_response):
        if not self.referrers or self.check_referrer(environ):
            return self.app(environ, start_response)
        else:
            return self.restricted_response(environ, start_response)
            
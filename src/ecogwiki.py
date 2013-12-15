#!/usr/bin/python

import os
import json
import httplib
import urlparse
import urllib
import logging
from urllib2 import HTTPError

import oauth2 as oauth
import feedparser

from version import __version__

CWD = os.path.join(os.path.expanduser('~'), '.ecog')

client_id     = '576416393937-rmcaesbkv0rfdcq71l5ol9p3sbmv1qf9.apps.googleusercontent.com'
client_secret = 'f_7_soOcc_SZhlDzLfUB0d-t'
consumer = oauth.Consumer(client_id, client_secret)

# logging
LOG_DIR = os.path.join(CWD, 'log')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
formatter = logging.Formatter(fmt="%(asctime)s %(levelname)s %(message)s", datefmt='[%H:%M:%S]')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

info_handler = logging.FileHandler(os.path.join(LOG_DIR, 'info.log'))
info_handler.setLevel(logging.INFO)

debug_handler = logging.FileHandler(os.path.join(LOG_DIR, 'debug.log'))
debug_handler.setLevel(logging.DEBUG)

error_handler = logging.FileHandler(os.path.join(LOG_DIR, 'error.log'))
error_handler.setLevel(logging.ERROR)

logger.addHandler(info_handler)
#logger.addHandler(debug_handler)
logger.addHandler(error_handler)


#
def to_url(url, params={}):
    """Serialize as a URL for a GET request."""
    base_url = urlparse.urlparse(url)
    try:
        query = base_url.query
    except AttributeError:
        # must be python <2.5
        query = base_url[4]
    query = urlparse.parse_qs(query)
    for k, v in params.items():
        query.setdefault(k, []).append(v)
    #    
    try:
        scheme = base_url.scheme
        netloc = base_url.netloc
        path = base_url.path
        params = base_url.params
        fragment = base_url.fragment
    except AttributeError:
        # must be python <2.5
        scheme = base_url[0]
        netloc = base_url[1]
        path = base_url[2]
        params = base_url[3]
        fragment = base_url[5]
    # 
    url = (scheme, netloc, path, params,
           urllib.urlencode(query, True), fragment)
    return urlparse.urlunparse(url)


#
#
#

class EcogWiki(object):
    def __init__(self, baseurl, access_token=None):
        self.baseurl = baseurl # http://ecogwiki-jangxyz.appspot.com
        self.set_access_token(access_token)

    @staticmethod
    def _parse_feed(text):
        return feedparser.parse(text)

    def set_access_token(self, access_token):
        self.access_token = access_token
        self.client = oauth.Client(consumer, access_token)

    def _request(self, url, method='GET', format=None, body='', headers=None):
        # params
        params = {
            'oauth_version': '2.0',
        }
        if format:
            params['_type'] = format

        # headers
        headers = {} if not isinstance(headers, dict) else headers
        if method in ("POST", "PUT"):
            headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        if method in ("PUT", "DELETE"):
            params['_method'] = method

        # url
        url = to_url(url, params)
        logger.debug('[_request] %s %s', method, url)
        if body:
            logger.debug('[_request] body: %s', body)

        # do the request
        resp, content = self.client.request(url, method=method, body=body, headers=headers)
        logger.debug('[_request] response: %s', resp)
        logger.debug('[_request] content: %s', content)
        if resp['status'] != '200':
            status = int(resp['status'])
            msg    = httplib.responses.get(status, "Invalid response %d." % status)
            logger.debug("[_request] Error: %d %s", status, msg)
            raise HTTPError(url, status, msg, None, None)
        return resp, content

    def get(self, title, format='json', revision=None):
        logger.info('[get] %s format:%s revision:%s', title, format, str(revision))
        # form url
        url = urllib.basejoin(self.baseurl, title)
        if revision:
            url += '?rev=' + str(revision)
        # request
        try:
            resp, content = self._request(url, method='GET', format=format)
        except HTTPError as e:
            logger.error("[get] %d %s", e.code, e.msg)
            raise

        if format == 'json':
            content = json.loads(content)
        return resp, content

    def post(self, title, body, revision=None, comment=''):
        logger.info('[post] %s size: %d revision:%s comment:%s', title, len(body), revision, comment)
        if revision is None:
            _resp,data = self.get(title)
            revision = data['revision']
        url = urllib.basejoin(self.baseurl, title)
        data = urllib.urlencode({
            'title': title,
            'body': body,
            'revision': revision,
            'comment': comment or 'post by ecogwiki client',
        })
        try:
            resp, content = self._request(url, format='json', method='PUT', body=data)
            try:
                content = json.loads(content)
            except Exception as e:
                logger.error('[post] json load error: %s', e)
            return resp, content
        except HTTPError as e:
            logger.error("[post] %d %s", e.code, e.msg)
            raise

    def list(self):
        ''' shorthand for GET /sp.index?_type=atom '''
        logger.info('[list] /sp.index?_type=atom')
        url = urllib.basejoin(self.baseurl, 'sp.index')
        try:
            resp, content = self._request(url, format='atom')
            return self._parse_feed(content)
        except HTTPError as e:
            logger.error("[list] %d %s", e.code, e.msg)
            raise

    def all(self):
        ''' shorthand for GET /sp.titles?_type=json '''
        logger.info('[all] /sp.titles?_type=json')
        url = urllib.basejoin(self.baseurl, 'sp.titles')
        try:
            resp, content = self._request(url, format='json')
            return json.loads(content)
        except HTTPError as e:
            logger.error("[all] %d %s", e.code, e.msg)
            raise

    def recent(self):
        ''' shorthand for GET /sp.changes?_type=atom '''
        logger.info('[recent] /sp.changes?_type=atom')
        url = urllib.basejoin(self.baseurl, 'sp.changes')
        try:
            resp, content = self._request(url, format='atom')
            return self._parse_feed(content)
        except HTTPError as e:
            logger.error("[recent] %d %s", e.code, e.msg)
            raise

    def cat(self, title, revision=None):
        ''' shorthand for GET TITLE?_type=rawbody '''
        logger.info('[cat] %s revision:%s', title, str(revision))
        return self.get(title, format='rawbody', revision=revision)
    
    #def search(self, title):
    #    pass

    #def memo(self):
    #    pass

    #def render(self, body, open=False):
    #    ''' render markdown text into HTML '''
    #    pass



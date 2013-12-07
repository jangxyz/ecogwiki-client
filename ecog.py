#!/usr/bin/env python

import os
import sys
import time
import datetime
import json
import argparse
import collections
import tempfile
import httplib
import urlparse
import urllib
import subprocess
import logging
from urllib2 import HTTPError

import oauth2 as oauth
import feedparser

CWD = os.path.dirname(os.path.realpath(__file__))

client_id     = '576416393937-rmcaesbkv0rfdcq71l5ol9p3sbmv1qf9.apps.googleusercontent.com'
client_secret = 'f_7_soOcc_SZhlDzLfUB0d-t'
consumer = oauth.Consumer(client_id, client_secret)

# system editor
editor = os.environ.get('EDITOR', 'vi')

formatter = logging.Formatter(fmt="%(asctime)s %(levelname)s %(message)s", datefmt='[%H:%M:%S]')

#logging.basicConfig(filename='log/log', filemode='w', level=logging.INFO)
#logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", datefmt='[%H:%M:%S]')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

info_handler = logging.FileHandler(os.path.join(CWD, 'log', 'info.log'))
#info_handler.setFormatter(formatter)
info_handler.setLevel(logging.INFO)

debug_handler = logging.FileHandler(os.path.join(CWD, 'log', 'debug.log'))
#debug_handler.setFormatter(formatter)
debug_handler.setLevel(logging.DEBUG)

error_handler = logging.FileHandler(os.path.join(CWD, 'log', 'error.log'))
#error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)

logger.addHandler(info_handler)
logger.addHandler(debug_handler)
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
#   Start OAuth phase
#

def step1_get_request_token(consumer, host):
    # Step 1: Get a request token. This is a temporary token that is used for 
    # having the user authorize an access token and to sign the request to obtain 
    # said access token.
    if '.appspot.com' in host:
        host = "https://%s" % urlparse.urlparse(host).hostname
    request_token_url = "%s/_ah/OAuthGetRequestToken" % host
    params = {
        'oauth_version': '2.0',
        'oauth_callback': 'oob',
    }
    url = to_url(request_token_url, params)

    client = oauth.Client(consumer)
    resp, content = client.request(url, "GET")
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        logger.error("[step1] %d %s", status, msg)
        raise HTTPError(url, status, msg, None, None)

    request_token_dict = dict(urlparse.parse_qsl(content))
    request_token      = oauth.Token(request_token_dict['oauth_token'], request_token_dict['oauth_token_secret'])

    logger.info("Request Token: (%s, %s)", request_token.key, request_token.secret)

    return request_token

def step2_user_authorization(request_token, host):
    if '.appspot.com' in host:
        host = "https://%s" % urlparse.urlparse(host).hostname
    authorize_url = "%s/_ah/OAuthAuthorizeToken" % host.rstrip('/')

    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (authorize_url, request_token.key)
    print

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = 'n'
    while accepted.lower() != 'y':
        accepted = raw_input('Have you authorized me? (y/N) ')

    oauth_verifier = raw_input('What is the PIN? ')
    print

    return oauth_verifier

def step3_get_access_token(consumer, request_token, oauth_verifier, host):
    # Step 3: Once the consumer has redirected the user back to the oauth_callback
    # URL you can request the access token the user has approved. You use the 
    # request token to sign this request. After this is done you throw away the
    # request token and use the access token returned. You should store this 
    # access token somewhere safe, like a database, for future use.
    if '.appspot.com' in host:
        host = "https://%s" % urlparse.urlparse(host).hostname
    access_token_url = "%s/_ah/OAuthGetAccessToken" % host.rstrip('/')
    params = {
        'oauth_version': '2.0',
    }
    url = to_url(access_token_url, params)

    request_token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, request_token)
    resp, content = client.request(url, "POST")
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        logger.error("[step3] %d %s", status, msg)
        raise HTTPError(url, status, msg, None, None)

    access_token_dict = dict(urlparse.parse_qsl(content))
    access_token      = oauth.Token(access_token_dict['oauth_token'], access_token_dict['oauth_token_secret'])

    logger.info("Access Token: (%s, %s)", access_token.key, access_token.secret)

    return access_token


def oauth_dance(consumer, host):
    logger.debug("let the dance begin!")
    request_token  = step1_get_request_token(consumer, host)
    oauth_verifier = step2_user_authorization(request_token, host)
    access_token   = step3_get_access_token(consumer, request_token, oauth_verifier, host)
    logger.debug("dance time is over.")
    return access_token

def save_authfile(access_token, authfile):
    with open(authfile, 'w') as f:
        f.write(access_token.key + '\n')
        f.write(access_token.secret + '\n')
#
#   End of OAuth phase
#
#access_token = oauth.Token(access_token_dict['oauth_token'], access_token_dict['oauth_token_secret'])


def _request(consumer, access_token, url, method='GET', headers=None, body=None):
    client = oauth.Client(consumer, access_token)
    params = {
        'oauth_version': '2.0',
    }
    url = to_url(url, params)
    resp, content = client.request(url, method)
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        logger.error("[_request] %d %s", status, msg)
        raise HTTPError(url, status, msg, None, None)
    return resp, content

def get(consumer, access_token, url):
    ''' GET request resource '''
    client = oauth.Client(consumer, access_token)
    params = {
        'oauth_version': '2.0',
    }
    url = to_url(url, params)
    resp, content = client.request(url, "GET")
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        logger.error("[get] %d %s", status, msg)
        raise HTTPError(url, status, msg, None, None)
    print "Response Status Code: %s" % resp['status']
    print "Response body: %s" % content

    return content


def post(consumer, access_token, url):
    ''' POST resource '''
    now = datetime.datetime.now()
    url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/sandbox/%s?_type=json' % now.strftime("%Y%m%d-%H%M")
    client = oauth.Client(consumer, access_token)
    params = {
        'oauth_version': '2.0',
    }

    new_data = {
        'body': 'new body at [[%s]]' % now.strftime("%Y%m%d-%H%M"),
        'revision': 0,
        'comment': '- by ecogwiki client'
    }
    url = to_url(url, params)
    resp, content = client.request(url, "POST", 
        body=urllib.urlencode(new_data))
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        logger.error("[post] %d %s", status, msg)
        raise HTTPError(url, status, msg, None, None)
    print "Response Status Code: %s" % resp['status']
    print "Response body: %s" % content

    return content


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
        params = {
            'oauth_version': '2.0',
        }
        if format:
            params['_type'] = format

        url = to_url(url, params)
        logger.debug('[_request] %s %s', method, url)
        #pprint ('params:', req._split_url_string(urlparse.urlparse(uri)[4]))
        if body:
            logger.debug('[_request] body: %s', body)
        #
        resp, content = self.client.request(url, method, body=body)
        logger.debug('[_request] response: %s', resp)
        if resp['status'] != '200':
            status = int(resp['status'])
            msg    = httplib.responses.get(status, "Invalid response %d." % status)
            logger.error("[_request] %d %s", status, msg)
            raise HTTPError(url, status, msg, None, None)
        return resp, content

    def get(self, title, format='json', revision=None):
        logger.info('[get] %s format:%s revision:%s', title, format, str(revision))
        # form url
        url = urllib.basejoin(self.baseurl, title)
        if revision:
            url += '?rev=' + str(revision)
        # request
        resp, content = self._request(url, format=format)
        if format == 'json':
            content = json.loads(content)
        return content

    def post(self, title, body, revision=None, comment=''):
        logger.info('[post] %s format:%s revision:%d comment:%s', title, format, int(revision), comment)
        if revision is None:
            data = self.get(title)
            revision = data['revision']
        url = urllib.basejoin(self.baseurl, title)
        data = urllib.urlencode({
            'title': title,
            'body': body,
            'revision': revision,
            'comment': comment or 'post by ecogwiki client',
        })
        resp, content = self._request(url, format='json', method='POST', body=data)
        content = json.loads(content)
        return content

    def list(self):
        ''' shorthand for GET /sp.index?_type=atom '''
        logger.info('[list] /sp.index?_type=atom')
        url = urllib.basejoin(self.baseurl, 'sp.index')
        resp, content = self._request(url, format='atom')
        return self._parse_feed(content)

    def all(self):
        ''' shorthand for GET /sp.titles?_type=json '''
        logger.info('[all] /sp.titles?_type=json')
        url = urllib.basejoin(self.baseurl, 'sp.titles')
        resp, content = self._request(url, format='json')
        return json.loads(content)

    def recent(self):
        ''' shorthand for GET /sp.changes?_type=atom '''
        logger.info('[recent] /sp.changes?_type=atom')
        url = urllib.basejoin(self.baseurl, 'sp.changes')
        resp, content = self._request(url, format='atom')
        return self._parse_feed(content)

    def cat(self, title, revision=None):
        ''' shorthand for GET TITLE?_type=rawbody '''
        logger.info('[cat] %s revision:%s', title, str(revision))
        return self.get(title, format='rawbody', revision=revision)

    def edit(self, title, comment='', r0_template=None):
        ''' open editor and send post after save 

        1. get page metadata and save
        2. get page rawdata with revision and save
        3. open tempfile with rawbody
        4. after save, read tempfile and confirm content
        5. ask comment
        6. post page with new content
        7. remove temp files
        '''
        logger.info('[edit] %s', title)
        if r0_template and not r0_template.endswith("\n"):
            r0_template += "\n\n"

        tempdir = tempfile.mkdtemp(prefix='ecogwiki-')
        logger.debug('[edit] temp directory: %s', tempdir)
        try:
            # 1. get page metadata
            jsondata   = self.get(title, format='json')
            safe_title = urllib.quote_plus(title)
            fd, temp_json = tempfile.mkstemp(dir=tempdir, prefix=safe_title+'-', suffix='.json')
            logger.debug('[edit] "%s" meta file: %s', title, temp_json)
            try:
                with open(temp_json, 'w') as f:
                    json.dump(jsondata, f, indent=4)
                # 2. get page rawdata
                revision = jsondata['revision']
                rawbody  = self.get(title, format='rawbody', revision=revision)
                fd, temp_rawbody = tempfile.mkstemp(dir=tempdir, prefix='%s.r%d-' % (safe_title, revision), suffix='.markdown')
                logger.debug('[edit] "%s" rawbody file: %s', title, temp_rawbody)
                try:
                    with open(temp_rawbody, 'w') as f:
                        if revision > 0:
                            f.write(rawbody)
                        elif r0_template:
                            f.write(r0_template)
                    # 3. open temp file with editor
                    ret = subprocess.call(editor.split() + [temp_rawbody])
                    if ret != 0:
                        print 'editor %s failed with status %d, aborting.' % (editor, ret)
                        return
                    # 4. confirm content
                    content = ''
                    with open(temp_rawbody) as f:
                        content = f.read()
                    if (revision > 0 and content == rawbody) or (revision == 0 and content == r0_template):
                        print 'nothing new, aborting.'
                        return
                    if len(content) == 0:
                        print 'empty content, aborting.'
                        return
                    # 5. ask comment
                    if not comment:
                        comment = raw_input('comment message (default: written by ecogwiki client): ')
                        comment = comment or 'post by ecogwiki client'
                    # 6. post page with new content
                    result = self.post(title, content, revision=revision, comment=comment)
                    logger.debug('[edit] %s', result)
                    print 'updated %s to revision %d' % (title, int(result['revision']))
                    return result
                finally:
                    try:
                        os.remove(temp_rawbody)
                    except OSError as e:
                        logger.error('[edit] %s', e)
            finally:
                try:
                    os.remove(temp_json)
                except OSError as e:
                    logger.error('[edit] %s', e)
        finally:
            try:
                os.removedirs(tempdir)
            except OSError as e:
                logger.error('[edit] %s', e)
    
    #def search(self, title):
    #    pass

    #def memo(self):
    #    pass

    #def render(self, body, open=False):
    #    ''' render markdown text into HTML '''
    #    pass


if __name__ == '__main__':
    #
    # args
    #
    parser = argparse.ArgumentParser(description='Ecogwiki client', epilog='Information in your fingertips.')

    parser.add_argument('--auth', metavar='FILE', dest='authfile', default='.auth',
                       help='auth file storing access token')
    parser.add_argument('--host', metavar='HOST', dest='ecoghost', default='www.ecogwiki.com',
                       help='ecogwiki server host')

    subparsers = parser.add_subparsers(metavar='COMMAND', dest='command', help='ecogwiki commands')
    cat_parser    = subparsers.add_parser('cat',    help='print page in markdown')
    get_parser    = subparsers.add_parser('get',    help='print page in json')
    list_parser   = subparsers.add_parser('list',   help="list pages info")
    title_parser  = subparsers.add_parser('title',  help='list all titles')
    recent_parser = subparsers.add_parser('recent', help='list recent modified pages')
    edit_parser   = subparsers.add_parser('edit',   help='edit page with editor')
    memo_parser   = subparsers.add_parser('memo',   help='quick memo')
    
    edit_parser.add_argument('title', metavar='TITLE', help='page title')
    edit_parser.add_argument('--template', metavar='TEXT', help='text on new file', default=None)
    edit_parser.add_argument('--comment',  metavar='TEXT', help='edit comment message', default='')
    memo_parser.add_argument('--comment',  metavar='TEXT', help='edit comment message', default='')
    get_parser.add_argument('title', metavar='TITLE', help='page title')
    cat_parser.add_argument('title', metavar='TITLE', help='page title')
    get_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)
    cat_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)
    get_parser.add_argument('--format', metavar='FORMAT', help='one of [json|html|markdown|atom], json by default',
        choices=['json', 'rawbody', 'body', 'atom', 'markdown', 'html'], default='json')

    args = parser.parse_args()
    if '://' not in args.ecoghost:
        args.ecoghost = 'http://' + args.ecoghost

    logger.info('args: %s', args)

    # auth
    access_token = None
    if not args.authfile.startswith('/'):
        args.authfile = os.path.join(CWD, args.authfile)
    if os.path.exists(args.authfile):
        # read from auth file
        logger.debug('found auth file at: %s', args.authfile)
        token, secret = open(args.authfile).read().strip().split('\n')
        access_token  = oauth.Token(token, secret)
        logger.debug('access token: %s', access_token.key)

    # EcoWiki
    ecog = EcogWiki(args.ecoghost, access_token)

    #
    # Commands
    #
    now = datetime.datetime.now()
    def require_authorization(consumer, host):
        access_token = oauth_dance(consumer, host)
        print "You may now access protected resources using the access tokens above." 
        accepted = raw_input('Do you want to save access token for later? (Y/n) ')
        if accepted != 'n':
            save_authfile(access_token, args.authfile)
        else:
            print 'very well...'
        print
        return access_token

    def try_auth_on_forbidden(command):
        def run(*args, **kwargs):
            try:
                command(*args, **kwargs)
            except HTTPError as e:
                if e.code == 403 and ecog.access_token is None:
                    # authorize
                    yn = raw_input('Access is restricted. Do you want to authorize? (Y/n) ')
                    if yn.lower() == 'y':
                        print

                        access_token = require_authorization(consumer, ecog.baseurl)
                        ecog.set_access_token(access_token)
                        # retry
                        try:
                            command(*args, **kwargs)
                        except HTTPError as e:
                            print e.code, e.msg
                            sys.exit(e.code)
                    else:
                        print e.code, e.msg
                        sys.exit(e.code)
                else:
                    print e.code, e.msg
                    sys.exit(e.code)
        return run

    def updated_datetime(entry):
        timestamp = int(time.strftime("%s", entry.updated_parsed))
        return datetime.datetime.fromtimestamp(timestamp)
    def format_updated_datetime(dt):
        if now - dt <= datetime.timedelta(days=180):
            updated_time = time.strftime("%m %d %H:%M", entry.updated_parsed)
        else:
            updated_time = time.strftime("%m %d  %Y", entry.updated_parsed)
        return updated_time

    # list
    if args.command == 'list':
        entries = ecog.list().entries
        max_author_width = max(len(e.author) for e in entries)
        for entry in entries:
            dt = updated_datetime(entry)
            print("%s  %s  %s" % (
                entry.author.ljust(max_author_width), 
                format_updated_datetime(dt),
                entry.title
            ))

    # recents
    elif args.command == 'recent':
        entries = ecog.recent().entries
        def summary_size(entry):
            size = 0
            try:
                size = len(entry.summary)
            except:
                logger.warning('no summary for entry: %s', entry.title)
            return size

        max_author_width = max(len(e.author) for e in entries)
        summary_sizes    = [summary_size(e)  for e in entries]
        max_size_width   = len(str(max(summary_sizes)))

        for i,entry in enumerate(entries):
            dt = updated_datetime(entry)
            print("%s  %s  %s  %s" % (
                entry.author.ljust(max_author_width), 
                str(summary_size(entry)).rjust(max_size_width), 
                format_updated_datetime(dt),
                entry.title
            ))
        print

    # title
    elif args.command == 'title':
        for title in ecog.all():
            print title

    # get
    elif args.command == 'get':
        @try_auth_on_forbidden
        def get_command(title, revision, format):
            if format == 'html':     format = 'body'
            if format == 'markdown': format = 'rawbody'

            #
            content = ecog.get(title=title, revision=revision, format=format)

            if format == 'json':
                # sort by specific key order
                key_order = ["title", "revision", "updated_at", "modifier", "acl_read", "acl_write", "data", "body"]
                content = collections.OrderedDict(sorted(content.items(), key=lambda (k,v): key_order.index(k)))

                # trim body
                if content['body'] > 62: # 79 - 4(indent) - 6("body") - 2(: ) - 2("") - 3(...)
                    content['body'] = content['body'][:62] + '...'

                print json.dumps(content, indent=4)
            else:
                print content

        get_command(title=args.title, revision=args.revision, format=args.format)

    # cat
    elif args.command == 'cat':
        @try_auth_on_forbidden
        def cat_command(title, revision):
            content = ecog.cat(title=title, revision=revision)
            print content

        cat_command(title=args.title, revision=args.revision)

    # edit
    elif args.command == 'edit':
        @try_auth_on_forbidden
        def edit_command(title, r0_template, comment):
            ecog.edit(title=title, r0_template=r0_template, comment=comment)

        edit_command(title=args.title, r0_template=args.template, comment=args.comment)

    # memo
    elif args.command == 'memo':
        @try_auth_on_forbidden
        def memo_command(comment):
            title = 'memo/%s' % now.strftime("%y-%m-%d")
            ecog.edit(title=title, r0_template='.write janghwan@gmail.com\n', comment=comment)

        memo_command(comment=args.comment)



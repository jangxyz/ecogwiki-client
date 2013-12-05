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
from urllib2 import HTTPError

import oauth2 as oauth
import feedparser

CWD = os.path.dirname(os.path.realpath(__file__))

app_id = 'ecogwiki-jangxyz'
url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-1?_type=json'
url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-2?_type=json'

REQUEST_TOKEN_URL = lambda host: "https://%s/_ah/OAuthGetRequestToken" % host
AUTHORIZE_URL     = lambda host: "https://%s/_ah/OAuthAuthorizeToken"  % host
ACCESS_TOKEN_URL  = lambda host: "https://%s/_ah/OAuthGetAccessToken"  % host

client_id     = '576416393937-rmcaesbkv0rfdcq71l5ol9p3sbmv1qf9.apps.googleusercontent.com'
client_secret = 'f_7_soOcc_SZhlDzLfUB0d-t'
consumer = oauth.Consumer(client_id, client_secret)


# system editor
editor = os.environ.get('EDITOR', 'vi')

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
    client = oauth.Client(consumer)
    params = {
        'oauth_version': '2.0',
        'oauth_callback': 'oob',
    }
    url = to_url(REQUEST_TOKEN_URL(urlparse.urlparse(host).hostname), params)
    resp, content = client.request(url, "GET")
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        raise HTTPError(url, status, msg, None, None)

    request_token_dict = dict(urlparse.parse_qsl(content))
    request_token      = oauth.Token(request_token_dict['oauth_token'], request_token_dict['oauth_token_secret'])

    print "Request Token:"
    print "    - oauth_token        = %s" % request_token.key
    print "    - oauth_token_secret = %s" % request_token.secret
    print 

    return request_token

def step2_user_authorization(request_token, host):
    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (AUTHORIZE_URL(urlparse.urlparse(host).hostname), request_token.key)
    print 

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = 'n'
    while accepted.lower() != 'y':
        accepted = raw_input('Have you authorized me? (y/N) ')

    oauth_verifier = raw_input('What is the PIN? ')

    return oauth_verifier

def step3_get_access_token(consumer, request_token, oauth_verifier, host):
    # Step 3: Once the consumer has redirected the user back to the oauth_callback
    # URL you can request the access token the user has approved. You use the 
    # request token to sign this request. After this is done you throw away the
    # request token and use the access token returned. You should store this 
    # access token somewhere safe, like a database, for future use.
    request_token.set_verifier(oauth_verifier)

    client = oauth.Client(consumer, request_token)
    params = {
        'oauth_version': '2.0',
    }
    url = to_url(ACCESS_TOKEN_URL(urlparse.urlparse(host).hostname), params)
    resp, content = client.request(url, "POST")
    if resp['status'] != '200':
        status = int(resp['status'])
        msg    = httplib.responses.get(status, "Invalid response %d." % status)
        raise HTTPError(url, status, msg, None, None)

    access_token_dict = dict(urlparse.parse_qsl(content))
    access_token      = oauth.Token(access_token_dict['oauth_token'], access_token_dict['oauth_token_secret'])

    print "Access Token:"
    print "    - oauth_token        = %s" % access_token.key
    print "    - oauth_token_secret = %s" % access_token.secret
    print
    print "You may now access protected resources using the access tokens above." 
    print

    return access_token

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
        raise HTTPError(url, status, msg, None, None)
    print "Response Status Code: %s" % resp['status']
    print "Response body: %s" % content

    return content


#
#
#

class EcogWiki(object):
    def __init__(self, url, access_token=None):
        self.url = url # http://ecogwiki-jangxyz.appspot.com
        self.set_access_token(access_token)

    def auth(self):
        pass

    def set_access_token(self, access_token):
        self.access_token = access_token
        self.client = oauth.Client(consumer, access_token)

    @staticmethod
    def _parse_feed(text):
        return feedparser.parse(text)

    def _request(self, url, method='GET', format=None, body='', headers=None):
        params = {
            'oauth_version': '2.0',
        }
        if format:
            params['_type'] = format

        url = to_url(url, params)
        resp, content = self.client.request(url, method, body=body)
        if resp['status'] != '200':
            status = int(resp['status'])
            msg    = httplib.responses.get(status, "Invalid response %d." % status)
            raise HTTPError(url, status, msg, None, None)
        return resp, content

    def get(self, title, format='json', revision=None):
        url = urllib.basejoin(self.url, title)
        if revision:
            url += '?rev=' + str(revision)
        resp, content = self._request(url, format=format)
        if format == 'json':
            content = json.loads(content)
        return content

    def post(self, title, body, revision=None, comment=''):
        if revision is None:
            data = self.get(title)
            revision = data['revision']
        url = urllib.basejoin(self.url, title)
        data = urllib.urlencode({
            'title': title,
            'body': body,
            'revision': revision,
            'comment': comment or 'post by ecogwiki client',
        })
        resp, content = self._request(url, format='json', method='POST', body=data)
        return content

    def list(self):
        ''' shorthand for GET /sp.index?_type=atom '''
        url = urllib.basejoin(self.url, 'sp.index')
        resp, content = self._request(url, format='atom')
        return self._parse_feed(content)

    def all(self):
        ''' shorthand for GET /sp.titles?_type=json '''
        url = urllib.basejoin(self.url, 'sp.titles')
        resp, content = self._request(url, format='json')
        return json.loads(content)

    def recent(self):
        ''' shorthand for GET /sp.changes?_type=atom '''
        url = urllib.basejoin(self.url, 'sp.changes')
        resp, content = self._request(url, format='atom')
        return self._parse_feed(content)

    def cat(self, title, revision=None):
        ''' shorthand for GET TITLE?_type=rawbody '''
        return self.get(title, format='rawbody', revision=revision)

    def edit(self, title, r0_template=None):
        ''' open editor and send post after save 

        1. get page metadata and save
        2. get page rawdata with revision and save
        3. open tempfile with rawbody
        4. after save, read tempfile and confirm content
        5. ask comment
        6. post page with new content
        7. remove temp files
        '''
        if r0_template and not r0_template.endswith("\n"):
            r0_template += "\n\n"

        tempdir = tempfile.mkdtemp(prefix='ecogwiki-')
        print tempdir
        try:
            # 1. get page metadata
            jsondata   = self.get(title, format='json')
            safe_title = urllib.quote_plus(title)
            fd, temp_json = tempfile.mkstemp(dir=tempdir, prefix=safe_title+'-', suffix='.json')
            print 'json:', temp_json
            try:
                with open(temp_json, 'w') as f:
                    json.dump(jsondata, f, indent=4)
                # 2. get page rawdata
                revision = jsondata['revision']
                rawbody  = self.get(title, format='rawbody', revision=revision)
                fd, temp_rawbody = tempfile.mkstemp(dir=tempdir, prefix='%s.r%d-' % (safe_title, revision), suffix='.markdown')
                print 'rawbody:', temp_rawbody
                try:
                    with open(temp_rawbody, 'w') as f:
                        if revision > 0:
                            f.write(rawbody)
                        else:
                            f.write(r0_template)
                    # 3. open temp file with editor
                    ret = subprocess.call([editor, temp_rawbody])
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
                    comment = raw_input('comment (default: written by ecogwiki client): ')
                    comment = comment or 'post by ecogwiki client'
                    # 6. post page with new content
                    result = self.post(title, content, revision=revision, comment=comment)
                    print result
                finally:
                    try:
                        os.remove(temp_rawbody)
                    except OSError as e:
                        print e
            finally:
                try:
                    os.remove(temp_json)
                except OSError as e:
                    print e
        finally:
            try:
                os.removedirs(tempdir)
            except OSError as e:
                print e
    
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
    get_parser.add_argument('title', metavar='TITLE', help='page title')
    cat_parser.add_argument('title', metavar='TITLE', help='page title')
    get_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)
    cat_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)

    args = parser.parse_args()
    if '://' not in args.ecoghost:
        args.ecoghost = 'http://' + args.ecoghost

    # auth
    if not args.authfile.startswith('/'):
        args.authfile = os.path.join(CWD, args.authfile)
    if os.path.exists(args.authfile):
        # read from auth file
        token, secret = open(args.authfile).read().strip().split('\n')
        access_token  = oauth.Token(token, secret)
    else:
        # OAuth authorization
        request_token  = step1_get_request_token(consumer, args.ecoghost)
        oauth_verifier = step2_user_authorization(request_token, args.ecoghost)
        access_token   = step3_get_access_token(consumer, request_token, oauth_verifier, args.ecoghost)
        # save to auth file
        accepted = 'n'
        while accepted.lower() == 'n':
            accepted = raw_input('Do you want to save access token for later? (Y/n) ')
        with open(args.authfile, 'w') as f:
            f.write(access_token.key + '\n')
            f.write(access_token.secret + '\n')

    # EcoWiki
    ecog = EcogWiki(args.ecoghost, access_token)
    now  = datetime.datetime.now()

    #
    # Commands
    #

    # list
    if args.command == 'list':
        for entry in ecog.list().entries:
            dt = datetime.datetime.fromtimestamp(int(time.strftime("%s", entry.updated_parsed)))
            if now - dt <= datetime.timedelta(days=180):
                updated_time = time.strftime("%m %d %H:%M", entry.updated_parsed)
            else:
                updated_time = time.strftime("%m %d  %Y", entry.updated_parsed)

            print "%s %s %s" % (entry.author, updated_time, entry.title)
        print

    # title
    elif args.command == 'title':
        for title in ecog.all():
            print title

    # recents
    elif args.command == 'recent':
        for entry in ecog.recent().entries:
            dt = datetime.datetime.fromtimestamp(int(time.strftime("%s", entry.updated_parsed)))
            if now - dt <= datetime.timedelta(days=180):
                updated_time = time.strftime("%m %d %H:%M", entry.updated_parsed)
            else:
                updated_time = time.strftime("%m %d  %Y", entry.updated_parsed)

            size = 0
            try:
                size = len(entry.summary)
            except:
                pass
            print "%s %d %s %s" % (entry.author, size, updated_time, entry.title)
        print

    # get
    elif args.command == 'get':
        try:
            content = ecog.get(title=args.title, revision=args.revision)

            # sort by specific key order
            key_order = ["title", "revision", "updated_at", "modifier", "acl_read", "acl_write", "data", "body"]
            content = collections.OrderedDict(sorted(content.items(), key=lambda (k,v): key_order.index(k)))
            # trim body
            if content['body'] > 62: # 79 - 4(indent) - 6("body") - 2(: ) - 2("") - 3(...)
                content['body'] = content['body'][:62] + '...'

            print json.dumps(content, indent=4)
        except HTTPError as e:
            print e.code, e.msg
            sys.exit(e.code)

    # cat
    elif args.command == 'cat':
        try:
            content = ecog.cat(title=args.title, revision=args.revision)
            print(content)
        except HTTPError as e:
            print e.code, e.msg
            sys.exit(e.code)

    # edit
    elif args.command == 'edit':
        try:
            ecog.edit(title=args.title, r0_template=args.template)
        except HTTPError as e:
            print e.code, e.msg
            sys.exit(e.code)

    # memo
    elif args.command == 'memo':
        try:
            title = 'memo/%s' % now.strftime("%Y-%m-%d")
            ecog.edit(title=title, r0_template='.write janghwan@gmail.com\n')
        except HTTPError as e:
            print e.code, e.msg
            sys.exit(e.code)


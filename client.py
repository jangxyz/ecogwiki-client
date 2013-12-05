import os
import sys
import time
import datetime
import json
import argparse
import collections
import pprint
import urlparse, urllib
import oauth2 as oauth

import feedparser

CWD = os.path.dirname(os.path.realpath(__file__))

app_id = 'ecogwiki-jangxyz'
url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-1?_type=json'
url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-2?_type=json'

REQUEST_TOKEN_URL = "https://%s.appspot.com/_ah/OAuthGetRequestToken" % app_id
AUTHORIZE_URL     = "https://%s.appspot.com/_ah/OAuthAuthorizeToken"  % app_id
ACCESS_TOKEN_URL  = "https://%s.appspot.com/_ah/OAuthGetAccessToken"  % app_id

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


def step1_get_request_token(consumer):
    # Step 1: Get a request token. This is a temporary token that is used for 
    # having the user authorize an access token and to sign the request to obtain 
    # said access token.
    client = oauth.Client(consumer)
    params = {
        'oauth_version': '2.0',
        'oauth_callback': 'oob',
    }
    resp, content = client.request(to_url(REQUEST_TOKEN_URL, params), "GET")
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])

    request_token_dict = dict(urlparse.parse_qsl(content))
    request_token      = oauth.Token(request_token_dict['oauth_token'], request_token_dict['oauth_token_secret'])

    print "Request Token:"
    print "    - oauth_token        = %s" % request_token.key
    print "    - oauth_token_secret = %s" % request_token.secret
    print 

    return request_token



def step2_user_authorization(request_token):
    # Step2
    #
    #
    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (AUTHORIZE_URL, request_token.key)
    print 

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = 'n'
    while accepted.lower() == 'n':
            accepted = raw_input('Have you authorized me? (y/n) ')

    oauth_verifier = raw_input('What is the PIN? ')

    return oauth_verifier

def step3_get_access_token(consumer, request_token, oauth_verifier):
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
    resp, content = client.request(to_url(ACCESS_TOKEN_URL, params), "POST")

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
    resp, content = client.request(to_url(url, params), method)
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])
    return resp, content

def get(consumer, access_token, url):
    ''' GET request resource '''
    client = oauth.Client(consumer, access_token)
    params = {
        'oauth_version': '2.0',
    }
    resp, content = client.request(to_url(url, params), "GET")
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])
    print "Response Status Code: %s" % resp['status']
    print "Response body: %s" % content

    return content


def post(consumer, access_token, url):
    ''' POST resource '''
    from datetime import datetime
    now = datetime.now()
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
    resp, content = client.request(to_url(url, params), "POST", 
        body=urllib.urlencode(new_data))
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])
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

    def _request(self, url, method='GET', format=None, body='', headers=None):
        params = {
            'oauth_version': '2.0',
        }
        if format:
            params['_type'] = format
        resp, content = self.client.request(to_url(url, params), method, body=body)
        if resp['status'] != '200':
            raise Exception("Invalid response %s." % resp['status'])
        return resp, content

    @staticmethod
    def _highlight(text, format='markdown'):
        return pprint.pformat(text)
        #from pygments import highlight
        #from pygments.formatters import Terminal256Formatter
        #from pygments.lexers import get_lexer_by_name

    @staticmethod
    def _parse_feed(text):
        return feedparser.parse(text)

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

    def get(self, title, format='json'):
        url = urllib.basejoin(self.url, title)
        resp, content = self._request(url, format=format)
        if format == 'json':
            content = json.loads(content)
        return content

    def cat(self, title):
        ''' shorthand for GET TITLE?_type=rawbody '''
        url = urllib.basejoin(self.url, title)
        resp, content = self._request(url, format='rawbody')
        return content

    def post(self, title, body, revision=None, comment=''):
        if revision is None:
            data = self.get(title)
            revision = data['revision']
        url = urllib.basejoin(self.url, title)
        body = urllib.urlencode({
            'title': title,
            'body': body,
            'revision': revision,
            'comment': comment or 'post by ecogwiki client',
        })
        resp, content = self._request(url, format='json', method='POST', body=body)
        print content
        return content

    def edit(self, title):
        pass
    
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
    
    # cat
    cat_parser.add_argument('title', metavar='TITLE', help='page title')
    # get
    get_parser.add_argument('title', metavar='TITLE', help='page title')

    args = parser.parse_args()

    # auth
    if not args.authfile.startswith('/'):
        args.authfile = os.path.join(CWD, args.authfile)
    if os.path.exists(args.authfile):
        token, secret = open(os.path.join(CWD, '.auth')).read().strip().split('\n')
        access_token  = oauth.Token(token, secret)
    else:
        request_token  = step1_get_request_token(consumer)
        oauth_verifier = step2_user_authorization(request_token)
        access_token   = step3_get_access_token(consumer, request_token, oauth_verifier)

    #ecog = EcogWiki('http://ecogwiki-jangxyz.appspot.com', access_token)

    if '://' not in args.ecoghost:
        args.ecoghost = 'http://' + args.ecoghost
    ecog = EcogWiki(args.ecoghost, access_token)
    now  = datetime.datetime.now()

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
        content = ecog.get(title=args.title)

        # sort by specific key order
        key_order = ["title", "revision", "updated_at", "modifier", "acl_read", "acl_write", "data", "body"]
        content = collections.OrderedDict(sorted(content.items(), key=lambda (k,v): key_order.index(k)))
        if content['body'] > 62: # 79 - 4(indent) - 6("body") - 2(: ) - 2("") - 3(...)
            content['body'] = content['body'][:62] + '...'

        print json.dumps(content, indent=4, sort_keys=False)

    # cat
    elif args.command == 'cat':
        content = ecog.cat(title=args.title)
        print(content)

    # edit
    #


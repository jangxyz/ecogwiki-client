import os
import json
import urlparse, urllib
import oauth2 as oauth

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
        self.url = url # 'http://ecogwiki-jangxyz.appspot.com'
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

    def _highlight(self, text, format='markdown'):
        import pprint
        return pprint.pformat(text)
        #from pygments import highlight
        #from pygments.formatters import Terminal256Formatter
        #from pygments.lexers import get_lexer_by_name

    def list(self):
        ''' shorthand for GET /sp.index?_type=atom '''
        url = urllib.basejoin(self.url, 'sp.index')
        resp, content = self._request(url, format='atom')
        print self._highlight(content)

    def all(self):
        ''' shorthand for GET /sp.titles?_type=json '''
        url = urllib.basejoin(self.url, 'sp.titles')
        resp, content = self._request(url, format='json')
        print self._highlight(json.loads(content))

    def recent(self):
        ''' shorthand for GET /sp.changes?_type=atom '''
        url = urllib.basejoin(self.url, 'sp.changes')
        resp, content = self._request(url, format='atom')
        print self._highlight(content)

    def get(self, title, format='json'):
        url = urllib.basejoin(self.url, title)
        resp, content = self._request(url, format=format)
        if format == 'json':
            content = json.loads(content)
        print self._highlight(content)
        return content

    def cat(self, title):
        ''' shorthand for GET TITLE?_type=rawbody '''
        url = urllib.basejoin(self.url, title)
        resp, content = self._request(url, format='rawbody')
        print content
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
    
    def search(self, title):
        pass

    def memo(self):
        pass

    def render(self, body, open=False):
        ''' render markdown text into HTML '''
        pass


if __name__ == '__main__':
    # auth
    request_token  = step1_get_request_token(consumer)
    oauth_verifier = step2_user_authorization(request_token)
    access_token   = step3_get_access_token(consumer, request_token, oauth_verifier)

    # request resource
    content = get(consumer, access_token, url)

    print content



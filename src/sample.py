#!/usr/bin/python

'''

    Basic implementation of oauth with appengine.

    Not actually used in code.


'''

import datetime
import httplib
import urlparse
import urllib
from urllib2 import HTTPError

import oauth2 as oauth

client_id     = '576416393937-rmcaesbkv0rfdcq71l5ol9p3sbmv1qf9.apps.googleusercontent.com'
client_secret = 'f_7_soOcc_SZhlDzLfUB0d-t'
consumer = oauth.Consumer(client_id, client_secret)


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
        print "ERROR: [step1] %d %s", status, msg
        raise HTTPError(url, status, msg, None, None)

    request_token_dict = dict(urlparse.parse_qsl(content))
    request_token      = oauth.Token(request_token_dict['oauth_token'], request_token_dict['oauth_token_secret'])

    print "Request Token: (%s, %s)" % (request_token.key, request_token.secret)

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
        print "ERROR: [step3] %d %s", status, msg
        raise HTTPError(url, status, msg, None, None)

    access_token_dict = dict(urlparse.parse_qsl(content))
    access_token      = oauth.Token(access_token_dict['oauth_token'], access_token_dict['oauth_token_secret'])

    print "Access Token: (%s, %s)" % (access_token.key, access_token.secret)

    return access_token


def oauth_dance(consumer, host):
    print "let the dance begin!"
    request_token  = step1_get_request_token(consumer, host)
    oauth_verifier = step2_user_authorization(request_token, host)
    access_token   = step3_get_access_token(consumer, request_token, oauth_verifier, host)
    print "dance time is over."
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
        print "[_request] Error: %d %s" % (status, msg)
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
        print "ERROR: [get] %d %s" % (status, msg)
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
        print "ERROR: [post] %d %s" % (status, msg)
        raise HTTPError(url, status, msg, None, None)
    print "Response Status Code: %s" % resp['status']
    print "Response body: %s" % content

    return content


if __name__ == '__main__':
    consumer = oauth.Consumer(client_id, client_secret)

    # auth
    request_token  = step1_get_request_token(consumer)
    oauth_verifier = step2_user_authorization(request_token)
    access_token   = step3_get_access_token(consumer, request_token, oauth_verifier)

    # request resource
    url = 'http://ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-2?_type=json'
    content = get(consumer, access_token, url)

    print content


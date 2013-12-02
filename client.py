import oauth2 as oauth
import urlparse, urllib

app_id = 'oauth.ecogwiki-jangxyz'
url = 'http://oauth.ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-1?_type=json'
url = 'http://oauth.ecogwiki-jangxyz.appspot.com/ecogwiki/client/example-2?_type=json'

REQUEST_TOKEN_URL = "https://%s.appspot.com/_ah/OAuthGetRequestToken" % app_id
AUTHORIZE_URL     = "https://%s.appspot.com/_ah/OAuthAuthorizeToken"  % app_id
ACCESS_TOKEN_URL  = "https://%s.appspot.com/_ah/OAuthGetAccessToken"  % app_id

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


# Request resource
client = oauth.Client(consumer, access_token)
params = {
    'oauth_version': '2.0',
}
resp, content = client.request(to_url(url,params), "GET")
if resp['status'] != '200':
    raise Exception("Invalid response %s." % resp['status'])
print "Response Status Code: %s" % resp['status']
print "Response body: %s" % content



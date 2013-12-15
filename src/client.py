#!/usr/bin/python

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
import traceback
import difflib
import shutil

import oauth2 as oauth
import dateutil.parser

from version import __version__
from ecogwiki import EcogWiki
from ecogwiki import HTTPError

CWD = os.path.join(os.path.expanduser('~'), '.ecog')

client_id     = '576416393937-rmcaesbkv0rfdcq71l5ol9p3sbmv1qf9.apps.googleusercontent.com'
client_secret = 'f_7_soOcc_SZhlDzLfUB0d-t'
consumer = oauth.Consumer(client_id, client_secret)

# system editor
editor = os.environ.get('EDITOR', 'vi')

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


def output(*args, **kwargs):
    ''' print output to screen, using the default filesystem encoding

    output(*strings, sep=' ', end='\n', encoding=None, out=sys.stdout)

    '''
    sep      = kwargs.get('sep', ' ')
    end      = kwargs.get('end', '\n')
    encoding = kwargs.get('encoding', sys.getfilesystemencoding())
    out = kwargs.get('out', sys.stdout)
    for i,arg in enumerate(args):
        if i > 0:
            out.write(sep)
        arg = arg.encode(encoding) if isinstance(arg, unicode) else str(arg)
        out.write(arg)
    if end:
        out.write(end)


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

    output("Go to the following link in your browser:")
    output("%s?oauth_token=%s" % (authorize_url, request_token.key))
    output()

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = 'n'
    while accepted.lower() != 'y':
        accepted = raw_input('Have you authorized me? (y/N) ')

    oauth_verifier = raw_input('What is the PIN? ')
    output()

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


def parse_args():
    parser = argparse.ArgumentParser(prog='ecog', description='Ecogwiki client - Information in your fingertips', epilog=' ')
    parser.add_argument('--auth', metavar='FILE', dest='authfile', default='.auth',
                       help='auth file storing access token')
    parser.add_argument('--host', metavar='HOST', dest='ecoghost', default='www.ecogwiki.com',
                       help='ecogwiki server host')
    parser.add_argument('--version',  action='version', version='%(prog)s ' + __version__, default=None)

    subparsers = parser.add_subparsers(metavar='COMMAND', dest='command', title='ecogwiki commands')
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


    #
    args = parser.parse_args()

    if '://' not in args.ecoghost:
        args.ecoghost = 'http://' + args.ecoghost

    if args.version:
        output(__version__)
        sys.exit(0)

    return args

def main():
    args = parse_args()

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
    # Application Helpers
    #
    now = datetime.datetime.now()

    def require_authorization(consumer, host):
        access_token = oauth_dance(consumer, host)
        output("You may now access protected resources using the access tokens above." )
        accepted = raw_input('Do you want to save access token for later? (Y/n) ')
        if accepted != 'n':
            save_authfile(access_token, args.authfile)
        else:
            output('very well...')
        output()
        return access_token

    def try_auth_on_forbidden(ecog):
        ''' if request failed with 403 Forbidden, guide user to auth, and try once more.

        '''
        def command_runner(command):
            def run(*args, **kwargs):
                try:
                    return command(*args, **kwargs)
                except HTTPError as e:
                    if e.code == 403 and ecog.access_token is None:
                        # authorize
                        yn = raw_input('Access is restricted. Do you want to authorize? (Y/n) ')
                        if yn.lower() == 'y':
                            output()

                            access_token = require_authorization(consumer, ecog.baseurl)
                            ecog.set_access_token(access_token)
                            # retry
                            try:
                                # actual command is run here.
                                return command(*args, **kwargs)
                            except HTTPError as e:
                                raise
                    raise
            return run
        return command_runner

    def updated_datetime(entry):
        timestamp = int(time.strftime("%s", entry.updated_parsed))
        return datetime.datetime.fromtimestamp(timestamp)
    def format_updated_datetime(dt):
        if now - dt <= datetime.timedelta(days=180):
            updated_time = time.strftime("%m %d %H:%M", entry.updated_parsed)
        else:
            updated_time = time.strftime("%m %d  %Y", entry.updated_parsed)
        return updated_time

    #
    # Commands
    #
    @try_auth_on_forbidden(ecog)
    def edit_command(title, r0_template, comment):
        ''' open editor and send post after save 

        1. [GET] get page metadata and save temp file
        2. [GET] get page rawdata with revision and save temp file
        3. open tempfile with rawbody, and let user edit
        4. after edit is finished, confirm tempfile
        5. ask for comment
        6. [POST] post page with new content
        7. remove temp files
        '''
        logger.info('[edit] %s', title)
        if r0_template and not r0_template.endswith("\n"):
            r0_template += "\n\n"

        tempdir = tempfile.mkdtemp(prefix='ecogwiki-')
        logger.debug('[edit] temp directory: %s', tempdir)
        try:
            # 1. [GET] get page metadata
            ecog_get       = try_auth_on_forbidden(ecog)(ecog.get)
            _resp,jsondata = ecog_get(title, format='json')
            revision       = jsondata['revision']

            updated_at = None
            if jsondata['updated_at']:
                updated_at_str = jsondata['updated_at']
                updated_at_utc = dateutil.parser.parse(updated_at_str)              # parse ISO format
                updated_at     = updated_at_utc.astimezone(dateutil.tz.tzlocal())   # convert to local timezone

            safe_title = urllib.quote_plus(title)
            fd, temp_json = tempfile.mkstemp(dir=tempdir, prefix=safe_title+'-', suffix='.json')
            logger.debug('[edit] "%s" meta file: %s', title, temp_json)
            try:
                with open(temp_json, 'w') as f:
                    json.dump(jsondata, f, indent=4)
                # 2. [GET] get page rawdata
                rawbody = ecog_get(title, format='rawbody', revision=revision)
                fd, temp_rawbody0 = tempfile.mkstemp(dir=tempdir, prefix='%s.r%d-' % (safe_title, revision), suffix='.markdown')
                logger.debug('[edit] "%s" rawbody file: %s', title, temp_rawbody0)
                with open(temp_rawbody0, 'w') as f:
                    if revision > 0:
                        f.write(rawbody)
                    elif r0_template:
                        f.write(r0_template)
                # copy
                temp_rawbody = os.path.splitext(temp_rawbody0)
                temp_rawbody = temp_rawbody[0] + '.edit' + temp_rawbody[1]
                shutil.copy(temp_rawbody0, temp_rawbody)
                logger.debug('[edit] copy %s => %s', temp_rawbody0, temp_rawbody)
                try:
                    # 3. open temp file with editor
                    ret = subprocess.call(editor.split() + [temp_rawbody])
                    if ret != 0:
                        output('editor %s failed with status %d, aborting.' % (editor, ret))
                        return
                    # 4. confirm content
                    content = ''
                    with open(temp_rawbody) as f:
                        content = f.read()
                    if (revision > 0 and content == rawbody) or (revision == 0 and content == r0_template):
                        output('nothing new, aborting.')
                        return
                    if len(content) == 0:
                        output('empty content, aborting.')
                        return
                    # 5. ask comment
                    if not comment:
                        options = {
                            'n': 0,
                            'fromfile': '%s (rev %d)' % (title, revision),
                            'tofile': 'EDIT', 
                        }
                        if updated_at:
                            options['fromfiledate'] = updated_at.strftime("%Y/%m/%d %H-%M")

                        diff = difflib.unified_diff(rawbody.splitlines(True),content.splitlines(True), **options)
                        for line in diff:
                            output(line, end='')
                        comment = raw_input('comment message (default: written by ecogwiki client): ')
                        comment = comment or 'post by ecogwiki client'
                    # 6. [POST] post page with new content
                    ecog_post = try_auth_on_forbidden(ecog)(ecog.post)
                    resp, result = ecog_post(title, content, revision=revision, comment=comment)
                    logger.debug('[edit] %s', result)
                    #output('updated "%s" to revision %d: %s' % (title, int(new_revision), resp['location']))
                    ## 6.1 [GET] check page back
                    new_revision = ecog_get(title, format='json')['revision']
                    output('updated "%s" to revision %d' % (title, int(new_revision)))

                    # 7. remove temp file on success
                    try:
                        os.remove(temp_rawbody)
                        logger.debug('[edit] removed %s', temp_rawbody)
                    except OSError as e:
                        logger.error('[edit] failed removing temp rawbody file %s, %s', temp_rawbody, e)
                    try:
                        os.remove(temp_rawbody0)
                        logger.debug('[edit] removed %s', temp_rawbody0)
                    except OSError as e:
                        logger.error('[edit] failed removing temp rawbody file %s, %s', temp_rawbody0, e)

                    return result
                except Exception as e:
                    output('error during edit. temporary file is saved at: %s' % temp_rawbody)
                    logger.error('[edit] %s', e)
                    raise
                finally:
                    pass
            finally:
                try:
                    os.remove(temp_json)
                    logger.debug('[edit] removed %s', temp_json)
                except OSError as e:
                    logger.error('[edit] failed removing temp json file %s (%s)', temp_json, e)
        finally:
            try:
                os.removedirs(tempdir)
                logger.debug('[edit] removed %s', tempdir)
            except OSError as e:
                logger.error('[edit] failed removing temp directory %s, %s', tempdir, e)

    # list
    if args.command == 'list':
        try:
            entries = ecog.list().entries
            max_author_width = max(len(e.author) for e in entries)
            for entry in entries:
                dt = updated_datetime(entry)
                output("%s  %s  %s" % (
                    entry.author.ljust(max_author_width), 
                    format_updated_datetime(dt),
                    entry.title
                ))
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)

    # recents
    elif args.command == 'recent':
        def summary_size(entry):
            size = 0
            try:
                size = len(entry.summary)
            except:
                logger.warning('no summary for entry: %s', entry.title)
            return size
        try:
            entries = ecog.recent().entries

            max_author_width = max(len(e.author) for e in entries)
            summary_sizes    = [summary_size(e)  for e in entries]
            max_size_width   = len(str(max(summary_sizes)))

            for i,entry in enumerate(entries):
                dt = updated_datetime(entry)
                output("%s  %s  %s  %s" % (
                    entry.author.ljust(max_author_width), 
                    str(summary_size(entry)).rjust(max_size_width), 
                    format_updated_datetime(dt),
                    entry.title
                ))
            output()
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)

    # title
    elif args.command == 'title':
        try:
            for title in ecog.all():
                output(title)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)

    # get
    elif args.command == 'get':
        @try_auth_on_forbidden(ecog)
        def get_command(title, revision, format):
            if format == 'html':     format = 'body'
            if format == 'markdown': format = 'rawbody'

            #
            _resp,content = ecog.get(title=title, revision=revision, format=format)

            if format == 'json':
                # sort by specific key order
                key_order = ["title", "revision", "updated_at", "modifier", "acl_read", "acl_write", "data", "body"]
                content = collections.OrderedDict(sorted(content.items(), key=lambda (k,v): key_order.index(k)))

                # trim body
                if len(content['body']) > 62: # 79 - 4(indent) - 6("body") - 2(: ) - 2("") - 3(...)
                    content['body'] = content['body'][:62] + '...'

                output(json.dumps(content, indent=4))
            else:
                output(content)

        try:
            get_command(title=args.title, revision=args.revision, format=args.format)
        except HTTPError as e:
            logger.error(traceback.format_exc())
            output(e.code, e.msg)
            sys.exit(e.code/100)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)
        except Exception as e:
            logger.error(traceback.format_exc())
            output('program halt. see %s for traceback' % os.path.join(CWD, 'log/error.log'))
            sys.exit(1)

    # cat
    elif args.command == 'cat':
        @try_auth_on_forbidden(ecog)
        def cat_command(title, revision):
            _resp,content = ecog.cat(title=title, revision=revision)
            output(content)

        try:
            cat_command(title=args.title, revision=args.revision)
        except HTTPError as e:
            logger.error(traceback.format_exc())
            output(e.code, e.msg)
            sys.exit(e.code/100)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)
        except Exception as e:
            logger.error(traceback.format_exc())
            output('program halt. see %s for traceback' % os.path.join(CWD, 'log/error.log'))
            sys.exit(1)

    # edit
    elif args.command == 'edit':
        try:
            edit_command(title=args.title, r0_template=args.template, comment=args.comment)
        except HTTPError as e:
            logger.error(traceback.format_exc())
            output(e.code, e.msg)
            sys.exit(e.code/100)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)
        except Exception as e:
            logger.error(traceback.format_exc())
            output('program halt. see %s for traceback' % os.path.join(CWD, 'log/error.log'))
            sys.exit(1)

    # memo
    elif args.command == 'memo':
        try:
            title = 'memo/%s' % now.strftime("%Y-%m-%d")
            edit_command(title=title, r0_template='', comment=args.comment)
        except HTTPError as e:
            logger.error(traceback.format_exc())
            output(e.code, e.msg)
            sys.exit(e.code/100)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)
        except Exception as e:
            logger.error(traceback.format_exc())
            output('program halt. see %s for traceback' % os.path.join(CWD, 'log/error.log'))
            sys.exit(1)


if __name__ == '__main__':
    main()

# vim: sts=4 et

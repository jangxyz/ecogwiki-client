#!/usr/bin/python

'''

    usage: ecog [-h] [--auth FILE] [--host HOST] [--version] COMMAND ...

    Ecogwiki client - Information in your fingertips

    optional arguments:
      -h, --help   show this help message and exit
      --auth FILE  auth file storing access token
      --host HOST  ecogwiki server host
      --version    show program's version number and exit

    ecogwiki commands:
      COMMAND
            cat        print page in markdown
            get        print page in json
            list       list pages info
            title      list all titles
            recent     list recent modified pages
            edit       edit page with editor
            append     only append text
            memo       quick memo

'''

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
from contextlib import contextmanager

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



def updated_datetime(dtstr_iso):
    updated_at_utc = dateutil.parser.parse(dtstr_iso)                   # parse ISO format
    updated_at     = updated_at_utc.astimezone(dateutil.tz.tzlocal())   # convert to local timezone
    return updated_at

def format_updated_datetime(entry):
    dt  = updated_datetime(entry.updated)
    now = datetime.datetime.now(dateutil.tz.tzlocal())

    if now - dt <= datetime.timedelta(days=180):
        strfmt = "%m %d %H:%M"
    else:
        strfmt = "%m %d %H:%M"

    return dt.strftime(strfmt)

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



#
#   Decorators
#

def try_auth_on_forbidden(ecog, authfile):
    ''' if request failed with 403 Forbidden, guide user to auth, and try once more.

    '''

    def require_authorization(consumer, host):
        access_token = oauth_dance(consumer, host)
        output("You may now access protected resources using the access tokens above." )
        accepted = raw_input('Do you want to save access token for later? (Y/n) ')
        if accepted != 'n':
            save_authfile(access_token, authfile)
        else:
            output('very well...')
        output()
        return access_token

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


def exit_on_HTTPError(f):
    def run(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except HTTPError as e:
            logger.error(traceback.format_exc())
            output(e.code, e.msg)
            sys.exit(e.code/100)
    return run

def terminate_on_KeyboardInterrupt(f):
    def run(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            output("Terminating.")
            sys.exit(1)
    return run

def exit_on_exception(f):
    def run(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception:# as e:
            logger.error(traceback.format_exc())
            output('program halt. see %s for traceback' % os.path.join(CWD, 'log/error.log'))
            sys.exit(1)
    return run


COMMANDS = []
def command(f):
    COMMANDS.append(f.func_name)
    return f

#
#
#


class EcogClient(object):
    def __init__(self, ecoghost, authfile):
        self.authfile     = authfile # saved for later
        self.access_token = EcogClient.read_auth(authfile)
        #
        self.ecog = EcogWiki(ecoghost, self.access_token)

    @staticmethod
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
        edit_parser   = subparsers.add_parser('edit',   help='edit page with editor', description='Edit page with your favorite editor ($EDITOR)')
        append_parser = subparsers.add_parser('append', help='only append text',      description='Quickly append to page')
        memo_parser   = subparsers.add_parser('memo',   help='quick memo',            description='Edit your daily memo')
        
        edit_parser.add_argument('title', metavar='TITLE', help='page title')
        edit_parser.add_argument('--template', metavar='TEXT', help='text on new file', default=None)
        edit_parser.add_argument('--comment',  metavar='MSG',  help='edit comment message', default='')
        memo_parser.add_argument('--comment',  metavar='MSG',  help='edit comment message', default='')
        get_parser.add_argument('title', metavar='TITLE', help='page title')
        cat_parser.add_argument('title', metavar='TITLE', help='page title')
        get_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)
        cat_parser.add_argument('--revision', metavar='REV', help='specific revision number', type=int)
        get_parser.add_argument('--format', metavar='FORMAT', help='one of [json|html|markdown|atom], json by default',
            choices=['json', 'txt', 'atom', 'markdown', 'html'], default='json')

        append_parser.add_argument('title',           metavar='TITLE', help='page title')
        append_parser.add_argument('body', nargs='?', metavar='TEXT',  help='body text. fires editor if not given', default='')
        append_parser.add_argument('--comment',       metavar='MSG',   help='comment message', default='')

        #
        args = parser.parse_args()

        if '://' not in args.ecoghost:
            args.ecoghost = 'http://' + args.ecoghost

        if not args.authfile.startswith('/'):
            args.authfile = os.path.join(CWD, args.authfile)

        if args.version:
            output(__version__)
            sys.exit(0)

        return args

    @staticmethod
    def read_auth(authfile):
        access_token = None
        if os.path.exists(authfile):
            # read from auth file
            logger.debug('found auth file at: %s', authfile)
            token, secret = open(authfile).read().strip().split('\n')
            access_token  = oauth.Token(token, secret)
            logger.debug('access token: %s', access_token.key)
        return access_token

    @command
    def get(self, title, revision=None, format=None, **options): 
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        @exit_on_HTTPError
        @try_auth_on_forbidden(self.ecog, self.authfile)
        def _command(title, revision, format):
            if format == 'markdown': format = 'txt'

            #
            _resp,content = self.ecog.get(title=title, revision=revision, format=format)

            if format == 'json':
                # sort by some key order
                key_order = ["title", "revision", "updated_at", "modifier", "acl_read", "acl_write", "data", "body"]
                content = collections.OrderedDict(sorted(content.items(), key=lambda (k,v): key_order.index(k)))

                # trim body
                if len(content['body']) > 62: # 79 - 4(indent) - 6("body") - 2(: ) - 2("") - 3(...)
                    content['body'] = content['body'][:62] + '...'

                content = json.dumps(content, indent=4)

            output(content)

        _command(title=title, revision=revision, format=format)

    @command
    def cat(self, title, revision=None, **options): 
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        @exit_on_HTTPError
        @try_auth_on_forbidden(self.ecog, self.authfile)
        def _command(title, revision):
            _resp,content = self.ecog.cat(title=title, revision=revision)
            output(content)

        _command(title=title, revision=revision)

    @command
    def list(self, **options): 
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        def _command():
            entries = self.ecog.list().entries
            max_author_width = max(len(e.author) for e in entries)
            for entry in entries:
                output("%s  %s  %s" % (
                    entry.author.ljust(max_author_width), 
                    format_updated_datetime(entry),
                    entry.title
                ))
        _command()

    @command
    def title(self, **options): 
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        def _command():
            for title in self.ecog.all():
                output(title)
        _command()

    @command
    def recent(self, **options): 
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        def _command():
            entries = self.ecog.recent().entries

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
                output("%s  %s  %s  %s" % (
                    entry.author.ljust(max_author_width), 
                    str(summary_size(entry)).rjust(max_size_width), 
                    format_updated_datetime(entry),
                    entry.title
                ))
            output()
        
        _command()


    @contextmanager
    def working_with_tempdir(self, prefix=None, **options):
        local_logger, logger_heading = logger, ''
        logger_option = options.get('logger', True)
        if   logger_option is False:    local_logger = None
        elif logger_option is True:     local_logger = logger
        elif isinstance(logger_option, basestring):
            logger_heading = '[' + logger_option + '] '

        # create temp directory
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        logger.debug('[edit] temp directory: %s', temp_dir)
        local_logger and local_logger.debug('%stemp directory: %s', logger_heading, temp_dir)

        try:
            yield temp_dir
        finally:
            try:
                os.removedirs(temp_dir)
                local_logger and local_logger.debug('%sremoved %s', logger_heading, temp_dir)
            except OSError as e:
                local_logger and local_logger.debug('%sfailed removing temp directory %s, %s', logger_heading, temp_dir, e)
        

    @contextmanager
    def working_with_tempfile(self, dir=None, prefix=None, suffix=None, **options):
        local_logger, logger_heading = logger, ''
        logger_option = options.get('logger', True)
        if   logger_option is False:    local_logger = None
        elif logger_option is True:     local_logger = logger
        elif isinstance(logger_option, basestring):
            logger_heading = '[' + logger_option + '] '

        remove_on_final = options.get('remove_on_final', True)

        # create temp file
        fd, temp_file = tempfile.mkstemp(dir=dir, prefix=prefix, suffix=suffix)
        local_logger and local_logger.debug('%smeta file: %s', logger_heading, temp_file)

        try:
            yield temp_file
        finally:
            if remove_on_final:
                try:
                    os.remove(temp_file)
                    logger.debug('%sremoved %s', logger_heading, temp_file)
                except OSError as e:
                    logger.error('%sfailed removing temp json file %s (%s)', logger_heading, temp_file, e)

    @command
    def edit(self, title, template, comment, **options): 
        ecog_get = try_auth_on_forbidden(self.ecog, self.authfile)(self.ecog.get)
        ecog_put = try_auth_on_forbidden(self.ecog, self.authfile)(self.ecog.put)

        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        @exit_on_HTTPError
        def _command(title, r0_template, comment=''):
            ''' open editor and send put after save 

            1. [GET] get page metadata and save temp file
            2. [GET] get page rawdata with revision and save temp file
            3. open tempfile with rawbody, and let user edit
            4. after edit is finished, confirm tempfile
            5. ask for comment
            6. [PUT] put page with new content
            7. remove temp files
            '''
            logger.info('[edit] %s', title)
            if r0_template and not r0_template.endswith("\n"):
                r0_template += "\n\n"

            #tempdir = tempfile.mkdtemp(prefix='ecogwiki-')
            #logger.debug('[edit] temp directory: %s', tempdir)
            #try:
            with self.working_with_tempdir(prefix='ecogwiki-', logger='edit') as tempdir:

                # 1. [GET] get page metadata
                _resp,jsondata = ecog_get(title, format='json')
                revision       = jsondata['revision']
                updated_at     = updated_datetime(jsondata['updated_at']) if jsondata['updated_at'] else None

                safe_title = urllib.quote_plus(title)
                #fd, temp_json = tempfile.mkstemp(dir=tempdir, prefix=safe_title+'-', suffix='.json')
                #logger.debug('[edit] "%s" meta file: %s', title, temp_json)
                #try:
                with self.working_with_tempfile(dir=tempdir, prefix=safe_title+'-', suffix='.json', logger='edit') as temp_json:
                    with open(temp_json, 'w') as f:
                        json.dump(jsondata, f, indent=4)
                    # 2. [GET] get page rawdata
                    _resp,rawbody = ecog_get(title, format='txt', revision=revision)
                    fd, temp_rawbody0 = tempfile.mkstemp(dir=tempdir, prefix='%s.r%d-' % (safe_title, revision), suffix='.markdown')
                    logger.debug('[edit] "%s" rawbody file: %s', title, temp_rawbody0)
                    with open(temp_rawbody0, 'w') as f:
                        if revision > 0:
                            f.write(rawbody)
                        elif r0_template:
                            f.write(r0_template)
                    # copy tempfile
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
                            def diff_lines(a_str,b_str,fromfile,tofile,fromfiledate=None,tofiledate=None):
                                options = { 'n': 0 }
                                if fromfile:     options['fromfile']     = fromfile
                                if tofile:       options['tofile']       = tofile
                                if fromfiledate: options['fromfiledate'] = fromfiledate
                                if tofiledate:   options['tofiledate']   = tofiledate

                                diff = difflib.unified_diff(a_str.splitlines(True),b_str.splitlines(True), **options)
                                return diff

                            # display diff lines
                            fromfile,fromfiledate = '%s (rev %d)' % (title, revision), updated_at.strftime("%Y/%m/%d %H-%M")
                            for line in diff_lines(rawbody,content, fromfile=fromfile, tofile='EDIT', 
                                    fromfiledate=updated_at.strftime("%Y/%m/%d %H-%M")):
                                output(line, end='')
                            comment = raw_input('comment message (default: %s): ' % self.ecog.DEFAULT_COMMENT)
                            comment = comment or self.ecog.DEFAULT_COMMENT
                        # 6. [PUT] put page with new content
                        resp,result = ecog_put(title, content, revision=revision, comment=comment)
                        logger.debug('[edit] %s', resp)
                        logger.debug('[edit] %s', result)
                        # TODO: add content-location
                        #output('updated "%s" to revision %d: %s' % (title, int(result['revision']), resp['content-location']))
                        output('updated "%s" to revision %d' % (title, int(result['revision'])))

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
                #finally:
                #    try:
                #        os.remove(temp_json)
                #        logger.debug('[edit] removed %s', temp_json)
                #    except OSError as e:
                #        logger.error('[edit] failed removing temp json file %s (%s)', temp_json, e)
            #finally:
            #    try:
            #        os.removedirs(tempdir)
            #        logger.debug('[edit] removed %s', tempdir)
            #    except OSError as e:
            #        logger.error('[edit] failed removing temp directory %s, %s', tempdir, e)

        _command(title=title, r0_template=template, comment=comment)

    @command
    def memo(self, template='', comment='', **options): 
        now = datetime.datetime.now(dateutil.tz.tzlocal())
        title = 'memo/%s' % now.strftime("%Y-%m-%d")
        # TODO: add default .write ME to template
        self.edit(title=title, template=template, comment=comment)

    @command
    def append(self, title, body='', comment='', **options):
        @exit_on_exception
        @terminate_on_KeyboardInterrupt
        @exit_on_HTTPError
        @try_auth_on_forbidden(self.ecog, self.authfile)
        def _command(title, body='', comment=''):
            ''' if body is given, send post right away

            if not, open editor and send post after save 
            '''
            logger.info('[append] %s', title)
            if body:
                body = body.rstrip('\n') + '\n'
                self.ecog.post(title=title, body=body, comment=comment)
                return

            tempdir = tempfile.mkdtemp(prefix='ecogwiki-')
            logger.debug('[append] temp directory: %s', tempdir)
            try:
                safe_title = urllib.quote_plus(title)
                fd, temp_part = tempfile.mkstemp(dir=tempdir, prefix=safe_title+'.part-', suffix='.markdown')
                logger.debug('[append] "%s" partial file: %s', title, temp_part)
                try:
                    # 3. open temp file with editor
                    ret = subprocess.call(editor.split() + [temp_part])
                    if ret != 0:
                        output('editor %s failed with status %d, aborting.' % (editor, ret))
                        return
                    # 4. confirm content
                    content = ''
                    with open(temp_part) as f:
                        content = f.read()
                    if len(content) == 0:
                        output('empty content, aborting.')
                        return
                    # 5. ask comment
                    if not comment:
                        comment = raw_input('comment message (default: %s): ' % self.ecog.DEFAULT_COMMENT)
                        comment = comment or self.ecog.DEFAULT_COMMENT
                    # 6. [PUT] put page with new content
                    resp,result = self.ecog.post(title, content, comment=comment)
                    logger.debug('[append] %s', resp)
                    logger.debug('[append] %s', result)
                    # TODO: add content-location
                    #output('updated "%s" to revision %d: %s' % (title, int(result['revision']), resp['content-location']))
                    output('append to "%s"' % (title))

                    # 7. remove temp file on success
                    try:
                        os.remove(temp_part)
                        logger.debug('[append] removed %s', temp_part)
                    except OSError as e:
                        logger.error('[append] failed removing temp partial file %s, %s', temp_part, e)

                    return result
                except Exception as e:
                    output('error during edit. temporary file is saved at: %s' % temp_part)
                    logger.error('[append] %s', e)
                    raise
                finally:
                    pass
            finally:
                try:
                    os.removedirs(tempdir)
                    logger.debug('[append] removed %s', tempdir)
                except OSError as e:
                    logger.error('[append] failed removing temp directory %s, %s', tempdir, e)

        _command(title, body=body, comment=comment)



def main():
    args   = EcogClient.parse_args()
    kwargs = dict(args._get_kwargs())

    ## auth
    #access_token = None
    #if os.path.exists(args.authfile):
    #    # read from auth file
    #    logger.debug('found auth file at: %s', args.authfile)
    #    token, secret = open(args.authfile).read().strip().split('\n')
    #    access_token  = oauth.Token(token, secret)
    #    logger.debug('access token: %s', access_token.key)
    #ecog = EcogWiki(args.ecoghost, access_token)

    # EcoWiki
    client = EcogClient(args.ecoghost, args.authfile)

    # Commands
    if args.command in COMMANDS:
        command = getattr(client, args.command) # client.get
        command(**kwargs)


if __name__ == '__main__':
    main()

# vim: sts=4 et

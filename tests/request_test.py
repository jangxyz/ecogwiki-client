#!/usr/bin/python
import unittest
import ecog

'''

'''

import urllib2

import mock
import oauth2 as oauth


BASE_URL = 'http://ecogwiki-jangxyz.appspot.com/'

def parse_query_dict(url):
    url_parsed = urllib2.urlparse.urlparse(url)
    query = url_parsed.query
    query_dict = dict(urllib2.urlparse.parse_qsl(query))
    return query_dict

def full_url_with_path(path):
    return urllib2.urlparse.urljoin(BASE_URL, path)


class EcogTestCase(unittest.TestCase):
    def setUp(self):
        access_token = oauth.Token('token', 'secent')
        self.ecog = ecog.EcogWiki(BASE_URL, access_token=access_token)

        # mock client
        self.ecog.client = mock.Mock()
        self.response = oauth.httplib2.Response({
            'status': '200',
            'content-type': 'application/json; charset=utf-8'
        })
        self.ecog.client.request.return_value = (self.response, '')

    def tearDown(self):
        pass

class DefaultRequestBehavior(EcogTestCase):
    def setUp(self):
        super(DefaultRequestBehavior, self).setUp()

    def tearDown(self):
        super(DefaultRequestBehavior, self).tearDown()

    def test_deliver_default_ingredients(self):
        self.ecog._request('http://ecogwiki-jangxyz.appspot.com/Home', 
            method='GET', 
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            }, 
            body='bring me anywhere',
        )

        # assert url
        args, kwargs = self.ecog.client.request.call_args
        requested_url = args[0]
        self.assertTrue(requested_url.startswith('http://ecogwiki-jangxyz.appspot.com/Home'))
        # assert other arguments
        self.ecog.client.request.assert_called_with(mock.ANY,
            method='GET',
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body='bring me anywhere',
        )


    def test__type_param_with_format_argument(self):
        '''calling with format=json becomes `?_type=json` '''
        self.ecog._request('http://ecogwiki-jangxyz.appspot.com/Home', 
            method='GET', 
            format='json',
        )
        # assert url
        args, kwargs = self.ecog.client.request.call_args
        query_dict = parse_query_dict(args[0])
        self.assertEqual(query_dict['_type'], 'json')

    def test_raise_HTTPError_when_status_is_not_200(self):
        #
        self.response['status'] = '500'
        self.assertRaises(ecog.HTTPError, 
            self.ecog._request, 'http://ecogwiki-jangxyz.appspot.com/Home')
        # even on other 200's
        self.response['status'] = '201'
        self.assertRaises(ecog.HTTPError, 
            self.ecog._request, 'http://ecogwiki-jangxyz.appspot.com/Home')


class Ecog_get(EcogTestCase):
    def setUp(self):
        super(Ecog_get, self).setUp()
        # mock _request
        self.ecog._request = mock.Mock()
        self.response = oauth.httplib2.Response({
            'status': '200',
            'content-type': 'application/json; charset=utf-8'
        })
        self.ecog._request.return_value = (self.response, '{}')

    def tearDown(self):
        super(Ecog_get, self).tearDown()

    def test_default_behvaior(self):
        self.ecog.get(title='Home')
        # assert
        self.ecog._request.assert_called_with(
            #'http://ecogwiki-jangxyz.appspot.com/Home',
            full_url_with_path('Home'),
            method='GET',
            format='json',
        )

    def test_revision_argument_is_binded_into_url(self):
        self.ecog.get(title='Home', revision=10)
        # assert ?rev=10
        args, kwargs = self.ecog._request.call_args
        query_dict = parse_query_dict(args[0])
        self.assertEqual(query_dict['rev'], '10')

    def test_returns_parsed_json(self):
        #
        self.ecog._request.return_value = (self.response, '[1,2,3]')
        resp,content = self.ecog.get(title='Home', revision=10)
        self.assertEqual(content, [1,2,3])
        #
        self.ecog._request.return_value = (self.response, '{"body": "a new content"}')
        resp, content = self.ecog.get(title='Home', revision=10)
        self.assertEqual(content, {'body': 'a new content'})


class Ecog_post(EcogTestCase):
    def setUp(self):
        super(Ecog_post, self).setUp()
        # mock _request
        self.ecog._request = mock.Mock()
        self.response = oauth.httplib2.Response({
            'status': '200',
            'content-type': 'application/json; charset=utf-8'
        })
        self.ecog._request.return_value = (self.response, '{}')

    def tearDown(self):
        super(Ecog_post, self).tearDown()

    def test_default_behvaior(self):
        self.ecog.post(title='Home', body='a new Home', revision=10, comment='testing comment')
        # assert
        self.ecog._request.assert_called_with(
            'http://ecogwiki-jangxyz.appspot.com/Home',
            method='PUT',
            format='json',
            body=mock.ANY,
        )
        # assert body
        args, kwargs = self.ecog._request.call_args
        bodystring = kwargs['body']
        self.assertIn('title=Home', bodystring)
        self.assertIn('body=a+new+Home', bodystring)
        self.assertIn('revision=10', bodystring)
        self.assertIn('comment=testing+comment', bodystring)

    def test_get_revision_beforehand_if_is_not_given(self):
        '''request GET for revision beforehand, if revision is not given'''
        # mock get
        self.ecog.get = mock.Mock(return_value=(None, {
            'revision': 11,
        }))
        # run
        self.ecog.post(title='Home', body='a new Home')
        # assert
        self.ecog.get.assert_called_once_with(mock.ANY)
        # assert using revision
        args, kwargs = self.ecog._request.call_args
        self.assertIn('revision=11', kwargs['body'])

    def test_default_comment(self):
        self.ecog.post(title='Home', body='a new Home', revision=10)
        # assert body
        args, kwargs = self.ecog._request.call_args
        self.assertIn('post+by+ecogwiki+client', kwargs['body'])


class Ecog_cat(EcogTestCase):
    def setUp(self):
        super(Ecog_cat, self).setUp()
        # mock _request
        self.ecog.get = mock.Mock()
        self.response = oauth.httplib2.Response({
            'status': '200',
            'content-type': 'application/json; charset=utf-8'
        })
        #self.ecog._request.return_value = (self.response, '{}')

    def tearDown(self):
        super(Ecog_cat, self).tearDown()

    def test_calls_get_with_format_txt(self):
        self.ecog.cat(title='Home')
        # assert
        args, kwargs = self.ecog.get.call_args
        self.assertEqual(kwargs['format'], 'txt')


class PUT_Request(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

class DELETE_Request(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass




if __name__ == '__main__':
    unittest.main()


# vim: sts=4 et

#!/usr/bin/python
import unittest
import mock

import ecog

'''

    Test EcogWikiClient

        get
        cat
        list
        title
        recent
        edit
        memo  

'''


import urllib2
import oauth2 as oauth


class EcogClient(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_client_exists(self):
        client = ecog.EcogClient()
        self.assertTrue(callable(client.get))
        self.assertTrue(callable(client.cat))
        self.assertTrue(callable(client.list))
        self.assertTrue(callable(client.title))
        self.assertTrue(callable(client.recent))
        self.assertTrue(callable(client.edit))
        self.assertTrue(callable(client.memo))


class ParseArgsTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


class EcogClientTestCase(unittest.TestCase):
    pass


class DefaultRequestBehavior(EcogClientTestCase):
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


if __name__ == '__main__':
    unittest.main()

# vim: sts=4 et

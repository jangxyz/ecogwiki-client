#!/usr/bin/python
import unittest
import ecog

'''

    test EcogWiki class

'''

import mock

class EcogWikiTestCase(unittest.TestCase):
    def setUp(self):
        baseurl = 'http://ecogwiki-jangxyz.appspot.com/'
        access_token = ecog.oauth.Token('token', 'secent')
        self.ecog = ecog.EcogWiki(baseurl, access_token=access_token)

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()


# vim: sts=4 et

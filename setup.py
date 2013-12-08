#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

    Ecogwiki OAuth client

    `ecog` is a python client that talks with [ecogwiki](http://www.ecogwiki.com/). It is configurable to talk with any other ecogwiki hosts.


"""

from setuptools import setup


setup(name='ecog',
    version='0.7.22',
    author = 'Janghwan Kim',
    author_email = 'janghwan@gmail.com',
    description = 'Ecogwiki OAuth client',
    long_description = __doc__,
    url = 'https://github.com/jangxyz/ecogwiki-client',

    py_modules = ['ecog'],
    scripts = ['ecog'],
    install_requires = ['oauth2', 'feedparser'],
)


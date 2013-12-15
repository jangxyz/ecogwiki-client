#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

    Ecogwiki OAuth client

    `ecog` is a python client that talks with [ecogwiki](http://www.ecogwiki.com/). It is configurable to talk with any other ecogwiki hosts.

    See https://github.com/jangxyz/ecogwiki-client for details.


"""

from setuptools import setup

def read_version():
    import sys
    import importlib
    sys.path.insert(0, 'src')
    try:
        v = importlib.import_module('version')
        return v.__version__
    finally:
        sys.path.pop(0)

setup(name='ecog',
    version=read_version(),
    author = 'Jang-hwan Kim',
    author_email = 'janghwan@gmail.com',
    description = 'Ecogwiki OAuth client',
    long_description = __doc__,
    url = 'https://github.com/jangxyz/ecogwiki-client',

    package_dir = {'ecog': 'src'},
    packages = ['ecog'],
    scripts = ['ecog'],
    install_requires = ['oauth2', 'feedparser', 'python-dateutil'],

    license = 'MIT License',
    platforms = ['POSIX'],
    keywords = ['oauth', 'markdown'],
    classifiers = [line.strip() for line in '''
        Development Status :: 3 - Alpha
        Environment :: Console
        Intended Audience :: Developers
        Intended Audience :: End Users/Desktop
        License :: OSI Approved :: MIT License
        Natural Language :: English
        Operating System :: POSIX
        Programming Language :: Python :: 2.7
        Topic :: Communications
        Topic :: Terminals
        Topic :: Text Processing
        Topic :: Utilities
    '''.strip().splitlines()]
)


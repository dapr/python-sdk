# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import re
import os

from setuptools import setup
from subprocess import check_output as run

exec(open('dapr/version.py').read())


def parse_version(v):
    versionPattern = r'\d+(=?\.(\d+(=?\.(\d+)*)*)*)*'
    regexMatcher = re.compile(versionPattern)
    return regexMatcher.search(v).group(0)


def is_release():
    tagged_version = run(['git', 'describe', '--tags']).decode('utf-8').strip()[1:]
    return tagged_version == __version__


name = 'dapr'
description = 'Dapr SDK for Python'
long_description = '''
Dapr is a portable, serverless, event-driven runtime that makes it easy for developers to
build resilient, stateless and stateful microservices that run on the cloud and edge and
embraces the diversity of languages and developer frameworks.

Dapr codifies the best practices for building microservice applications into open,
independent, building blocks that enable you to build portable applications with the language
and framework of your choice. Each building block is independent and you can use one, some,
or all of them in your application.
'''.lstrip()
version = __version__

# Get build number from GITHUB_RUN_NUMBER environment variable
build_number = os.environ.get('GITHUB_RUN_NUMBER', '0')

if not is_release():
    name += '-dev'
    version = f'{parse_version(__version__)}.dev{build_number}'
    description = 'Dapr SDK for python'
    long_description = 'This is the development build.'


setup(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
)

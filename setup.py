# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import re
import os

from setuptools import setup
from subprocess import check_output as run

# Load version in dapr package.
exec(open('dapr/version.py').read())
version = __version__


def parse_version(ver):
    """Parse version string from ver."""
    regexVersion = r'\d+(=?\.(\d+(=?\.(\d+)*)*)*)*'
    match = re.compile(regexVersion)
    return match.search(ver).group(0)


def is_release():
    """Returns True only if version in the code is equal to git tag."""
    tagged_version = run(['git', 'describe', '--tags', '--always']).decode('utf-8').strip()[1:]
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

# Get build number from GITHUB_RUN_NUMBER environment variable
build_number = os.environ.get('GITHUB_RUN_NUMBER', '0')

if not is_release():
    name += '-dev'
    version = f'{parse_version(__version__)}.dev{build_number}'
    description = 'Dapr SDK for python'
    long_description = 'This is the development build.'

print(f'package name: {name}, version: {version}', flush=True)


setup(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
)

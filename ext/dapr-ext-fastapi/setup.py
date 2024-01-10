# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os

from setuptools import setup

# Load version in dapr package.
version_info = {}
with open('dapr/ext/fastapi/version.py') as fp:
    exec(fp.read(), version_info)
__version__ = version_info['__version__']


def is_release():
    return '.dev' not in __version__


name = 'dapr-ext-fastapi'
version = __version__
description = 'The official release of Dapr FastAPI extension.'
long_description = """
This is the FastAPI extension for Dapr.

Dapr is a portable, serverless, event-driven runtime that makes it easy for developers to
build resilient, stateless and stateful microservices that run on the cloud and edge and
embraces the diversity of languages and developer frameworks.

Dapr codifies the best practices for building microservice applications into open,
independent, building blocks that enable you to build portable applications with the language
and framework of your choice. Each building block is independent and you can use one, some,
or all of them in your application.
""".lstrip()

# Get build number from GITHUB_RUN_NUMBER environment variable
build_number = os.environ.get('GITHUB_RUN_NUMBER', '0')

if not is_release():
    name += '-dev'
    version = f'{__version__}{build_number}'
    description = 'The developmental release for Dapr FastAPI extension.'
    long_description = 'This is the developmental release for Dapr FastAPI extension.'

print(f'package name: {name}, version: {version}', flush=True)


setup(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
)

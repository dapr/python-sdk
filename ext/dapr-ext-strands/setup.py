# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from packaging.requirements import Requirement
from setuptools import setup

# Load version in dapr package.
version_info = {}
with open('dapr/ext/strands/version.py') as fp:
    exec(fp.read(), version_info)
__version__ = version_info['__version__']


def is_release():
    return '.dev' not in __version__


name = 'dapr-ext-strands'
version = __version__
description = 'The official release of Dapr Python SDK Strands Agents Extension.'
long_description = """
This is the Dapr Session Manager extension for Strands Agents.

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

# Read dependencies from pyproject.toml (single source of truth)
with open('pyproject.toml', 'rb') as f:
    stable_requires = list(tomllib.load(f)['project']['dependencies'])

setup_kwargs = dict(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
    install_requires=stable_requires,
)

if not is_release():
    setup_kwargs['name'] += '-dev'
    setup_kwargs['version'] = f'{__version__}{build_number}'
    setup_kwargs['description'] = (
        'The developmental release for the Dapr Session Manager extension for Strands Agents'
    )
    setup_kwargs['long_description'] = (
        'This is the developmental release for the Dapr Session Manager extension for Strands Agents'
    )
    setup_kwargs['install_requires'] = [
        'dapr-dev' + r[len('dapr') :] if Requirement(r).name == 'dapr' else r
        for r in stable_requires
    ]

print(f'package name: {setup_kwargs["name"]}, version: {setup_kwargs["version"]}', flush=True)

setup(**setup_kwargs)

# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from setuptools import setup

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

setup(
    description=description,
    long_description=long_description,
)

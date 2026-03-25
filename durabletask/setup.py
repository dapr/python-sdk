# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from setuptools import setup

# Load version from version.py
version_info = {}
with open("durabletask/version.py") as fp:
    exec(fp.read(), version_info)
__version__ = version_info["__version__"]


def is_release():
    return ".dev" not in __version__


name = "durabletask-dapr"
version = __version__
description = "A Durable Task Client SDK for Python (Dapr)"

# Get build number from GITHUB_RUN_NUMBER environment variable
build_number = os.environ.get("GITHUB_RUN_NUMBER", "0")

if not is_release():
    name += "-dev"
    version = f"{__version__}{build_number}"
    description = "The developmental release of the Durable Task Client SDK for Python (Dapr)."

print(f"package name: {name}, version: {version}", flush=True)

setup(
    name=name,
    version=version,
    description=description,
)

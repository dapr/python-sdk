# ------------------------------------------------------------
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

from dapr.clients import DaprClient

with DaprClient() as d:
    key = 'secretKey'
    randomKey = 'random'
    storeName = 'localsecretstore'

    resp = d.get_secret(store_name=storeName, key=key)
    print('Got!')
    print(resp.secret)
    resp = d.get_bulk_secret(store_name=storeName)
    print('Got!')
    # Converts dict into sorted list of tuples for deterministic output.
    print(sorted(resp.secrets.items()))
    try:
        resp = d.get_secret(store_name=storeName, key=randomKey)
        print('Got!')
        print(resp.secret)
    except:
        print('Got expected error for accessing random key')

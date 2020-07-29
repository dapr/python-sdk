# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

from dapr.clients import DaprClient

with DaprClient() as d:
    key = 'secretKey'
    storeName = 'localsecretstore'

    resp = d.get_secret(store_name=storeName, key=key)
    print('Got!')
    print(resp._secret)

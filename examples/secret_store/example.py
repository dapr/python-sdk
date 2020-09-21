# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

from dapr.clients import DaprClient

with DaprClient() as d:
    key = 'secretKey'
    randomKey = "random"
    storeName = 'localsecretstore'

    resp = d.get_secret(store_name=storeName, key=key)
    print('Got!')
    print(resp.secret)
    try:
        resp = d.get_secret(store_name=storeName, key=randomKey)
        print('Got!')
        print(resp.secret)
    except:
        print("Got expected error for accessing random key")


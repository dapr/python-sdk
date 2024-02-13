"""
dapr run python3 state_store_query.py
"""

from dapr.clients import DaprClient

import json


with DaprClient() as d:
    store_name = 'statestore'

    # Query the state store

    query = open('query.json', 'r').read()
    res = d.query_state(store_name=store_name, query=query)
    for r in res.results:
        print(r.key, json.dumps(json.loads(str(r.value, 'UTF-8')), sort_keys=True))
    print('Token:', res.token)

    # Get more results using a pagination token

    query = open('query-token.json', 'r').read()
    res = d.query_state(store_name=store_name, query=query)
    for r in res.results:
        print(r.key, json.dumps(json.loads(str(r.value, 'UTF-8')), sort_keys=True))
    print('Token:', res.token)

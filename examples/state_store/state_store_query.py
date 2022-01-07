
"""
dapr run python3 state_store.py
"""

import grpc

from dapr.clients import DaprClient

with DaprClient() as d:
    storeName = 'statestore'
    query = '''
{
    "filter": {
        "OR": [
            {
                "EQ": { "value.person.org": "Dev Ops" }
            },
            {
                "AND": [
                    {
                        "EQ": { "value.person.org": "Finance" }
                    },
                    {
                        "IN": { "value.state": [ "CA", "WA" ] }
                    }
                ]
            }
        ]
    },
    "sort": [
        {
            "key": "value.state",
            "order": "DESC"
        },
        {
            "key": "value.person.id"
        }
    ],
    "page": {
        "limit": 3
    }
}
'''
    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    res = d.query_state_alpha1(store_name=storeName, query=query)
    for r in res.results:
        print(r.key)
        print(r.value)
    print(res.token)

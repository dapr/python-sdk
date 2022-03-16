"""
dapr run --app-id configexample --components-path components/ -- python3 configuration.py
"""

import asyncio
from time import sleep
from dapr.clients import DaprClient


async def executeConfiguration():
        with DaprClient() as d:
                storeName = 'configurationstore'

                key = 'orderId'

                # Wait for sidecar to be up within 20 seconds.
                d.wait(20)

                # Get one configuration by key.
                configuration = d.get_configuration(store_name=storeName, keys=[key], config_metadata={})
                print(f"Got key={configuration.items[0].key} value={configuration.items[0].value} version={configuration.items[0].version}", flush=True)

asyncio.run(executeConfiguration())
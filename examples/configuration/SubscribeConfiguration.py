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

                # Subscribe to configuration by key.
                configuration = await d.subscribe_configuration(store_name=storeName, keys=[key], config_metadata={})
                while True:
                        if configuration != None:
                                items = configuration.get_items()
                                for item in items:
                                        print(f"Subscribe key={item.key} value={item.value} version={item.version}", flush=True)
                        else:
                                print("Nothing yet")
                        sleep(5)

asyncio.run(executeConfiguration())
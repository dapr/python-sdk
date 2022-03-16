"""
dapr run python3 configuration.py
"""

import asyncio
from time import sleep
from dapr.clients import DaprClient

with DaprClient() as d:
                storeName = 'configurationstore'

                key = 'orderId'

                # Wait for sidecar to be up within 20 seconds.
                d.wait(20)

                # Subscribe to configuration by key.
                configuration = asyncio.run(d.subscribe_configuration(store_name=storeName, keys=[key], config_metadata={}))

                for i in range(10):
                        if configuration != None:
                                print(f"Subscribe key={configuration.get_dict}")
                                # print(f"Subscribe key={configuration.get_dict} value={configuration.items[0].value} version={configuration.items[0].version}")
                        else:
                                print("Nothing yet")
                        sleep(1)
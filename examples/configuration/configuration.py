"""
dapr run --app-id configexample --components-path components/ -- python3 configuration.py
"""

import asyncio
from time import sleep
from dapr.clients import DaprClient
from dapr.clients.grpc._response import ConfigurationWatcher

configuration: ConfigurationWatcher = ConfigurationWatcher()


async def executeConfiguration():
    with DaprClient() as d:
        storeName = 'configurationstore'

        keys = ['orderId1', 'orderId2']

        # Wait for sidecar to be up within 20 seconds.
        d.wait(20)

        global configuration

        # Get one configuration by key.
        configuration = d.get_configuration(store_name=storeName, keys=keys, config_metadata={})
        for key in configuration.items:
            print(f"Got key={key} "
                  f"value={configuration.items[key].value} "
                  f"version={configuration.items[key].version} "
                  f"metadata={configuration.items[key].metadata}", flush=True)

        # Subscribe to configuration by key.
        configuration = await d.subscribe_configuration(store_name=storeName, keys=keys,
                                                        config_metadata={})
        for x in range(5):
            if configuration is not None:
                print("Got configuration update", flush=True)
                items = configuration.get_items()
                for key in items:
                    print(f"Subscribe key={key} value={items[key].value} "
                          f"version={items[key].version} "
                          f"metadata={items[key].metadata}", flush=True)
            else:
                print("Nothing yet")
            sleep(3)

        # Unsubscribe from configuration
        isSuccess = d.unsubscribe_configuration(store_name=storeName, key=keys[1])
        print(f"Unsubscribed successfully? {isSuccess}", flush=True)

asyncio.run(executeConfiguration())

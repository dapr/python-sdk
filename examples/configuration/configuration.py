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

        keys = ['orderId', 'orderId1']

        # Wait for sidecar to be up within 20 seconds.
        d.wait(20)

        global configuration

        # Get one configuration by key.
        configuration = d.get_configuration(store_name=storeName, keys=keys, config_metadata={})
        print(f"Got key={configuration.items[0].key} "
              f"value={configuration.items[0].value} version={configuration.items[0].version} "
              f"metadata={configuration.items[0].metadata}", flush=True)
        print(f"Got key={configuration.items[1].key} value={configuration.items[1].value} "
              f"version={configuration.items[1].version} "
              f"metadata={configuration.items[1].metadata}", flush=True)

        # Subscribe to configuration by key.
        configuration = await d.subscribe_configuration(store_name=storeName, keys=keys,
                                                        config_metadata={})
        for x in range(10):
            if configuration is not None:
                items = configuration.get_items()
                for item in items:
                    print(f"Subscribe key={item.key} value={item.value} version={item.version} "
                          f"metadata={item.metadata}", flush=True)
            else:
                print("Nothing yet")
            sleep(5)

        # Unsubscribe from configuration
        isSuccess = d.unsubscribe_configuration(store_name=storeName, key=keys[1])
        print(f"Unsubscribed successfully? {isSuccess}", flush=True)

asyncio.run(executeConfiguration())

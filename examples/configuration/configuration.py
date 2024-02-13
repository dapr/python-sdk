"""
dapr run --app-id configexample --resources-path components/ -- python3 configuration.py
"""

import asyncio
from time import sleep
from dapr.clients import DaprClient
from dapr.clients.grpc._response import ConfigurationWatcher, ConfigurationResponse

configuration: ConfigurationWatcher = ConfigurationWatcher()


def handler(id: str, resp: ConfigurationResponse):
    for key in resp.items:
        print(
            f'Subscribe key={key} value={resp.items[key].value} '
            f'version={resp.items[key].version} '
            f'metadata={resp.items[key].metadata}',
            flush=True,
        )


async def executeConfiguration():
    with DaprClient() as d:
        storeName = 'configurationstore'

        keys = ['orderId1', 'orderId2']

        global configuration

        # Get one configuration by key.
        configuration = d.get_configuration(store_name=storeName, keys=keys, config_metadata={})
        for key in configuration.items:
            print(
                f'Got key={key} '
                f'value={configuration.items[key].value} '
                f'version={configuration.items[key].version} '
                f'metadata={configuration.items[key].metadata}',
                flush=True,
            )

        # Subscribe to configuration for keys {orderId1,orderId2}.
        id = d.subscribe_configuration(
            store_name=storeName, keys=keys, handler=handler, config_metadata={}
        )
        print('Subscription ID is', id, flush=True)
        sleep(10)

        # Unsubscribe from configuration
        isSuccess = d.unsubscribe_configuration(store_name=storeName, id=id)
        print(f'Unsubscribed successfully? {isSuccess}', flush=True)


asyncio.run(executeConfiguration())

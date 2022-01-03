
"""
dapr run python3 configuration.py
"""

from dapr.clients import DaprClient

with DaprClient() as d:
        storeName = 'configurationstore'

        key = 'greeting'

        # Wait for sidecar to be up within 5 seconds.
        d.wait(20)

        # Get one configuration by key.
        configuration = d.get_configuration(store_name=storeName, keys=[key], config_metadata={})
        print(f"Got key={configuration.items[0].key} value={configuration.items[0].value} version={configuration.items[0].version}")

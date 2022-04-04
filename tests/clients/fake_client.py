from typing import Dict, Optional

from dapr.proto.common.v1.common_pb2 import ConfigurationItem

class FakeDaprClient():
    async def subscribe_configuration(
            self, store_name: str, keys: str, config_metadata: Optional[Dict[str, str]] = dict()) -> ConfigurationItem:
        pass
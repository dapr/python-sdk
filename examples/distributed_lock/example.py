# ------------------------------------------------------------
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

from dapr.clients import DaprClient
import logging
import uuid


def main():
    # Lock parameters
    store_name = 'lockstore'  # as defined in components/lockstore.yaml
    resource_id = 'python-sdk-example-lock-resource'
    client_id = f'client-{str(uuid.uuid4())}'
    expiry_in_seconds = 60

    with DaprClient() as dapr:
        logging.info(f'Will attempt to acquire a lock for resource={resource_id}')
        logging.info(f'This client identifier is {client_id}')
        logging.info(f'This lock will will expire in {expiry_in_seconds} seconds.')

        with dapr.try_lock(store_name, resource_id, client_id, expiry_in_seconds) as lock_result:
            assert(lock_result.success)
            logging.info('Lock acquired successfully lock_result=%s', lock_result)

        # At this point the lock was released - by magic of the `with` clause ;)
        unlock_result = dapr.unlock(store_name, resource_id, client_id)
        logging.info("We already released the lock so unlocking will not work - unlock_result=%s",
                     unlock_result)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()

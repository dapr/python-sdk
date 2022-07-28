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
import warnings


def main():
    # Lock parameters
    store_name = 'lockstore'  # as defined in components/lockstore.yaml
    resource_id = 'example-lock-resource'
    client_id = 'example-client-id'
    expiry_in_seconds = 60

    with DaprClient() as dapr:
        logging.info(f'Will try to acquire a lock from "{store_name}" for resource={resource_id}')
        logging.info(f'This client identifier is "{client_id}"')
        logging.info(f'This lock will will expire in {expiry_in_seconds} seconds.')

        with dapr.try_lock(store_name, resource_id, client_id, expiry_in_seconds) as lock_result:
            assert(lock_result.success)
            logging.info('Lock acquired successfully')

        # At this point the lock was released - by magic of the `with` clause ;)
        unlock_result = dapr.unlock(store_name, resource_id, client_id)
        logging.info("We already released the lock so unlocking will not work - unlock status=%s",
                     unlock_result.status)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # Suppress "The Distributed Lock API is an Alpha" warnings
    warnings.simplefilter("ignore")
    main()

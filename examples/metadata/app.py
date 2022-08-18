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


def main():
    extended_attribute_name = 'is-this-our-metadata-example'

    with DaprClient() as dapr:
        print("First, we will assign a new custom label to Dapr sidecar")
        # We do this so example can be made deterministic across
        # multiple invocations.
        original_value = 'yes'
        dapr.set_metadata(extended_attribute_name, original_value)

        print("Now, we will fetch the sidecar's metadata")
        metadata = dapr.get_metadata()
        old_value = metadata.extended_metadata[extended_attribute_name]

        print("We will update our custom label value and check it was persisted")
        dapr.set_metadata(extended_attribute_name, 'You bet it is!')
        metadata = dapr.get_metadata()
        new_value = metadata.extended_metadata[extended_attribute_name]
        print("We added a custom label named [%s]" % extended_attribute_name)
        print("Its old value was [%s] but now it is [%s]" % (old_value, new_value))

        print("And we are done 👋", flush=True)


if __name__ == '__main__':
    main()

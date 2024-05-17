# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from dataclasses import dataclass

from dapr.proto import api_v1


@dataclass
class EncryptOptions:
    """EncryptOptions contains options passed to the encrypt method.

    Args:
        component_name (str): The name of the component.
        key_name (str): The name of the key to use for the encryption operation.
        key_wrap_algorithm (str): The key wrap algorithm to use.
        data_encryption_cipher (str, optional): The cipher to use for the encryption operation.
        omit_decryption_key_name (bool, optional): If True, omits the decryption key name from
            header `dapr-decryption-key-name` from the output. If False, includes the specified
            decryption key name specified in header `dapr-decryption-key-name`.
        decryption_key_name (str, optional): If `dapr-omit-decryption-key-name` is True, this
            contains the name of the intended decryption key to include in the output.
    """

    component_name: str
    key_name: str
    key_wrap_algorithm: str
    data_encryption_cipher: str = 'aes-gcm'
    omit_decryption_key_name: bool = False
    decryption_key_name: str = ''

    def get_proto(self) -> api_v1.EncryptRequestOptions:
        return api_v1.EncryptRequestOptions(
            component_name=self.component_name,
            key_name=self.key_name,
            key_wrap_algorithm=self.key_wrap_algorithm,
            data_encryption_cipher=self.data_encryption_cipher,
            omit_decryption_key_name=self.omit_decryption_key_name,
            decryption_key_name=self.decryption_key_name,
        )


@dataclass
class DecryptOptions:
    """DecryptOptions contains options passed to the decrypt method.

    Args:
        component_name (str): The name of the component.
        key_name (str, optional): The name of the key to use for the decryption operation.
    """

    component_name: str
    key_name: str = ''

    def get_proto(self) -> api_v1.DecryptRequestOptions:
        return api_v1.DecryptRequestOptions(
            component_name=self.component_name,
            key_name=self.key_name,
        )

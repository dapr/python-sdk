# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import asyncio
from tempfile import TemporaryFile

from dapr.aio.clients import DaprClient


async def main():
    data = bytes(range(256)) * 1024
    with TemporaryFile() as source, TemporaryFile() as destination:
        source.write(data)
        source.seek(0)
        async with DaprClient() as client:
            await client.set_binary_file_alpha1('binarystore', 'example/data.bin', source)
            response = await client.get_binary_file_alpha1('binarystore', 'example/data.bin')
            async with response:
                async for chunk in response:
                    await asyncio.to_thread(destination.write, chunk)
            destination.seek(0)
            assert destination.read() == data
            print(f'Binary file round trip: {len(data)} bytes')

            await client.set_binary_file_alpha1(
                'binarystore', 'example/data.bin', b'replaced', overwrite=True
            )
            response = await client.get_binary_file_alpha1('binarystore', 'example/data.bin')
            async with response:
                print(f'Overwritten file: {(await response.read()).decode()}')
            await client.delete_binary_file_alpha1('binarystore', 'example/data.bin')
            print('Binary file deleted')


if __name__ == '__main__':
    asyncio.run(main())

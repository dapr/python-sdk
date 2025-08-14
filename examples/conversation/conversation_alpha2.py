# ------------------------------------------------------------
# Copyright 2025 The Dapr Authors
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
from dapr.clients.grpc.conversation import (
    ConversationMessageContent,
    ConversationMessageOfUser,
    ConversationMessage,
    ConversationInputAlpha2,
)

with DaprClient() as d:
    inputs = [
        ConversationInputAlpha2(
            messages=[
                ConversationMessage(
                    of_user=ConversationMessageOfUser(
                        content=[ConversationMessageContent(text="What's Dapr?")]
                    )
                )
            ]
        ),
        ConversationInputAlpha2(
            messages=[
                ConversationMessage(
                    of_user=ConversationMessageOfUser(
                        content=[ConversationMessageContent(text='Give a brief overview.')]
                    )
                )
            ]
        ),
    ]

    metadata = {
        'model': 'foo',
        'key': 'authKey',
        'cacheTTL': '10m',
    }

    response = d.converse_alpha2(
        name='echo', inputs=inputs, temperature=0.7, context_id='chat-123', metadata=metadata
    )

    print('Result: ', end='')
    for output in response.outputs:
        print(output.choices[0].message.content)

#!/bin/bash

# ------------------------------------------------------------
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

# Path to store output
DAPR_BRANCH=${DAPR_BRANCH:-master}

if type "curl" > /dev/null; then
    HTTP_REQUEST_CLI=curl
elif type "wget" > /dev/null; then
    HTTP_REQUEST_CLI=wget
else
    echo "Either curl or wget is required"
    exit 1
fi

target="$(pwd)"

tmp="$(mktemp -d dapr-protos)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/dapr/dapr/archive/refs/heads/${DAPR_BRANCH}.tar.gz"

pushd "$tmp"
echo "Downloading Dapr from $url..."
if [ "$HTTP_REQUEST_CLI" == "curl" ]; then
    curl -SsL "$url" -o - | tar --strip-components=1 -xzf -
else
    wget -q -O - "$url" | tar --strip-components=1 -xzf -
fi
popd

python3 -m grpc_tools.protoc -I ${target} --proto_path="${tmp}" --python_out=${target} --grpc_python_out=${target} --mypy_out=${target} \
    "dapr/proto/common/v1/common.proto" \
    "dapr/proto/runtime/v1/appcallback.proto" \
    "dapr/proto/runtime/v1/dapr.proto" \
    "dapr/proto/runtime/v1/actors.proto" \
    "dapr/proto/runtime/v1/pubsub.proto" \
    "dapr/proto/runtime/v1/invoke.proto" \
    "dapr/proto/runtime/v1/state.proto" \
    "dapr/proto/runtime/v1/binding.proto" \
    "dapr/proto/runtime/v1/secret.proto" \
    "dapr/proto/runtime/v1/metadata.proto" \
    "dapr/proto/runtime/v1/configuration.proto" \
    "dapr/proto/runtime/v1/lock.proto" \
    "dapr/proto/runtime/v1/crypto.proto" \
    "dapr/proto/runtime/v1/workflow.proto" \
    "dapr/proto/runtime/v1/jobs.proto" \
    "dapr/proto/runtime/v1/ai.proto" \

echo -e "\ngRPC interface and proto buf generated successfully!"

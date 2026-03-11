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

files=("dapr/proto/common/v1/common.proto")
while IFS= read -r -d '' file; do
    files+=("$file")
done < <(find "dapr/proto/runtime/v1" -name '*.proto' -print0)

popd


python3 -m grpc_tools.protoc -I ${target} --proto_path="${tmp}" --python_out=${target} --grpc_python_out=${target} --mypy_out=${target} ${files[@]}
echo -e "\ngRPC interface and proto buf generated successfully!"

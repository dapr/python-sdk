#!/bin/bash

# ------------------------------------------------------------
# Copyright 2026 The Dapr Authors
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

# Regenerate Python protobuf/gRPC stubs for the vendored durabletask package.
#
# Proto source files are fetched from the durabletask-protobuf repository.
# Generated output goes to ext/dapr-ext-workflow/dapr/ext/workflow/_durabletask/internal/
#
# Prerequisites: uv sync --all-packages --group dev
#
# Usage:
#   ./tools/regen_durabletask_protos.sh
#   DURABLETASK_PROTOBUF_BRANCH=v1.2.3 ./tools/regen_durabletask_protos.sh

set -euo pipefail

DURABLETASK_PROTOBUF_BRANCH=${DURABLETASK_PROTOBUF_BRANCH:-main}
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/ext/dapr-ext-workflow/dapr/ext/workflow/_durabletask/internal"
PYTHON_PACKAGE="dapr.ext.workflow._durabletask.internal"

if type "curl" > /dev/null 2>&1; then
    HTTP_REQUEST_CLI=curl
elif type "wget" > /dev/null 2>&1; then
    HTTP_REQUEST_CLI=wget
else
    echo "Either curl or wget is required"
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/dapr/durabletask-protobuf/archive/refs/heads/${DURABLETASK_PROTOBUF_BRANCH}.tar.gz"

echo "Downloading durabletask-protobuf from ${url}..."
pushd "$tmp" > /dev/null
if [ "$HTTP_REQUEST_CLI" == "curl" ]; then
    curl -SsL "$url" -o - | tar --strip-components=1 -xzf -
else
    wget -q -O - "$url" | tar --strip-components=1 -xzf -
fi
popd > /dev/null

# The .proto files live under protos/ in durabletask-protobuf and use bare
# imports like: import "orchestration.proto"
#
# We use the protos directory as the single --proto_path so that bare imports
# resolve correctly. Generated files land directly in the output directory.
proto_dir="${tmp}/protos"

proto_files=()
while IFS= read -r -d '' file; do
    proto_files+=("$file")
done < <(find "${proto_dir}" -name '*.proto' -print0)

if [ ${#proto_files[@]} -eq 0 ]; then
    echo "Error: no .proto files found in durabletask-protobuf/protos/"
    exit 1
fi

echo "Found ${#proto_files[@]} proto file(s)"
echo "Generating Python stubs into ${OUTPUT_DIR}..."

python3 -m grpc_tools.protoc \
    --proto_path="${proto_dir}" \
    --python_out="${OUTPUT_DIR}" \
    --grpc_python_out="${OUTPUT_DIR}" \
    --mypy_out="${OUTPUT_DIR}" \
    "${proto_files[@]}"

# Fix imports in generated files to use the vendored package path.
# Since we used a flat --proto_path, protoc generates bare imports like:
#   import orchestration_pb2 as orchestration__pb2
#   from orchestration_pb2 import ...
# These must become:
#   from dapr.ext.workflow._durabletask.internal import orchestration_pb2 as orchestration__pb2
echo "Rewriting imports in generated files..."
for f in "${OUTPUT_DIR}"/*_pb2*.py "${OUTPUT_DIR}"/*_pb2*.pyi; do
    [ -f "$f" ] || continue
    if [[ "$(uname)" == "Darwin" ]]; then
        # Rewrite "import X_pb2" -> "from <package> import X_pb2"
        sed -i '' \
            -e "s|^import \([a-z_]*_pb2\)|from ${PYTHON_PACKAGE} import \1|g" \
            -e "s|^from \([a-z_]*_pb2\)|from ${PYTHON_PACKAGE}.\1|g" \
            -e "s|from durabletask\.internal|from ${PYTHON_PACKAGE}|g" \
            -e "s|import durabletask\.internal|import ${PYTHON_PACKAGE}|g" \
            "$f"
    else
        sed -i \
            -e "s|^import \([a-z_]*_pb2\)|from ${PYTHON_PACKAGE} import \1|g" \
            -e "s|^from \([a-z_]*_pb2\)|from ${PYTHON_PACKAGE}.\1|g" \
            -e "s|from durabletask\.internal|from ${PYTHON_PACKAGE}|g" \
            -e "s|import durabletask\.internal|import ${PYTHON_PACKAGE}|g" \
            "$f"
    fi
done

# Fix the BuildTopDescriptorsAndMessages call to use the vendored Python module path.
# This controls the Python module name registration in the protobuf descriptor pool.
echo "Rewriting module registration paths..."
for f in "${OUTPUT_DIR}"/*_pb2.py; do
    [ -f "$f" ] || continue
    # Replace bare module names like 'orchestrator_service_pb2' with full path.
    # protoc may use single or double quotes depending on version.
    basename_no_ext="$(basename "$f" .py)"
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' \
            -e "s|'${basename_no_ext}'|'${PYTHON_PACKAGE}.${basename_no_ext}'|g" \
            -e "s|\"${basename_no_ext}\"|\"${PYTHON_PACKAGE}.${basename_no_ext}\"|g" \
            "$f"
    else
        sed -i \
            -e "s|'${basename_no_ext}'|'${PYTHON_PACKAGE}.${basename_no_ext}'|g" \
            -e "s|\"${basename_no_ext}\"|\"${PYTHON_PACKAGE}.${basename_no_ext}\"|g" \
            "$f"
    fi
done

echo -e "\nDurableTask protobuf/gRPC stubs regenerated successfully!"
echo "Output: ${OUTPUT_DIR}"

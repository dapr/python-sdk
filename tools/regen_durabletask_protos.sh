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
# Proto source files are fetched from the durabletask-protobuf repository, or
# taken from a local checkout when DURABLETASK_PROTOBUF_DIR is set.
# Generated output goes to dapr/ext/workflow/_durabletask/internal/
#
# Prerequisites: uv sync --all-extras --group dev
#
# Usage:
#   ./tools/regen_durabletask_protos.sh
#   DURABLETASK_PROTOBUF_BRANCH=v1.2.3 ./tools/regen_durabletask_protos.sh
#   DURABLETASK_PROTOBUF_DIR=/path/to/durabletask-protobuf ./tools/regen_durabletask_protos.sh

set -euo pipefail

DURABLETASK_PROTOBUF_BRANCH=${DURABLETASK_PROTOBUF_BRANCH:-main}
DURABLETASK_PROTOBUF_DIR=${DURABLETASK_PROTOBUF_DIR:-}
proto_source_commit=""
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/dapr/ext/workflow/_durabletask/internal"
PYTHON_PACKAGE="dapr.ext.workflow._durabletask.internal"

if [ -n "$DURABLETASK_PROTOBUF_DIR" ]; then
    if [ ! -d "${DURABLETASK_PROTOBUF_DIR}/protos" ]; then
        echo "Error: ${DURABLETASK_PROTOBUF_DIR}/protos does not exist"
        exit 1
    fi
    echo "Using local durabletask-protobuf checkout at ${DURABLETASK_PROTOBUF_DIR}"
    proto_dir="${DURABLETASK_PROTOBUF_DIR}/protos"

    # The recorded commit is only meaningful if the protos it names are the ones
    # actually fed to protoc. Uncommitted or untracked proto changes would be
    # baked into the stubs while PROTO_SOURCE_COMMIT_HASH pointed at HEAD, so the
    # provenance would be a lie. Refuse instead: commit the proto change (or push
    # it upstream) and rerun.
    if [ -n "$(git -C "${DURABLETASK_PROTOBUF_DIR}" status --porcelain -- protos 2>/dev/null)" ]; then
        echo "Error: ${DURABLETASK_PROTOBUF_DIR}/protos has uncommitted or untracked changes."
        echo "The generated stubs would not match the commit recorded in PROTO_SOURCE_COMMIT_HASH."
        git -C "${DURABLETASK_PROTOBUF_DIR}" status --short -- protos
        exit 1
    fi

    proto_source_commit="$(git -C "${DURABLETASK_PROTOBUF_DIR}" rev-parse HEAD 2>/dev/null || true)"
else
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

    proto_dir="${tmp}/protos"

    # The tarball carries no git metadata, so resolve the branch head via the API.
    api_url="https://api.github.com/repos/dapr/durabletask-protobuf/commits/${DURABLETASK_PROTOBUF_BRANCH}"
    if [ "$HTTP_REQUEST_CLI" == "curl" ]; then
        proto_source_commit="$(curl -SsL -H 'Accept: application/vnd.github.sha' "$api_url" 2>/dev/null || true)"
    else
        proto_source_commit="$(wget -q -O - --header='Accept: application/vnd.github.sha' "$api_url" 2>/dev/null || true)"
    fi
fi

# The .proto files live under protos/ in durabletask-protobuf and use bare
# imports like: import "orchestration.proto"
#
# We use the protos directory as the single --proto_path so that bare imports
# resolve correctly. Generated files land directly in the output directory.

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

# Record which durabletask-protobuf commit produced these stubs. Without this
# the file is edited by hand and silently drifts from the generated code.
if [ -n "$proto_source_commit" ]; then
    echo "$proto_source_commit" > "${OUTPUT_DIR}/PROTO_SOURCE_COMMIT_HASH"
    echo "Recorded source commit ${proto_source_commit}"
else
    echo "Warning: could not resolve the durabletask-protobuf commit;" \
         "update ${OUTPUT_DIR}/PROTO_SOURCE_COMMIT_HASH by hand"
fi

echo -e "\nDurableTask protobuf/gRPC stubs regenerated successfully!"
echo "Output: ${OUTPUT_DIR}"

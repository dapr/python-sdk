#!/bin/bash

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

# Path to store output
PROTO_PATH="dapr/proto"
SRC=.

# Local dapr repository path (relative to current directory)
LOCAL_DAPR_PATH="../dapr"

checkLocalDaprRepo() {
    if [ ! -d "$LOCAL_DAPR_PATH" ]; then
        echo "Local dapr repository not found at: $LOCAL_DAPR_PATH"
        echo "Please ensure the dapr repository is cloned at the expected location."
        exit 1
    fi
    
    if [ ! -d "$LOCAL_DAPR_PATH/dapr/proto" ]; then
        echo "Proto directory not found at: $LOCAL_DAPR_PATH/dapr/proto"
        echo "Please ensure the dapr repository contains the proto files."
        exit 1
    fi
}

checkDependencies() {
    # Check if grpc_tools.protoc is available
    if ! python3 -c "import grpc_tools.protoc" 2>/dev/null; then
        echo "Error: grpcio-tools is not installed"
        echo "Please install it with: pip install -r tools/requirements.txt"
        exit 1
    fi
    
    # Check if protoc-gen-mypy is available
    if ! command -v protoc-gen-mypy &> /dev/null; then
        echo "Error: protoc-gen-mypy is not available"
        echo "Please install it with: pip install mypy-protobuf"
        exit 1
    fi
}

copyFile() {
    PKG_NAME=$1
    FILE_NAME=$2
    FILE_PATH="${PROTO_PATH}/${PKG_NAME}/v1"

    # Local path for proto file
    LOCAL_PROTO_PATH="${LOCAL_DAPR_PATH}/dapr/proto/${PKG_NAME}/v1/${FILE_NAME}.proto"

    mkdir -p "${FILE_PATH}"

    echo "Copying $LOCAL_PROTO_PATH ..."
    
    if [ ! -e "$LOCAL_PROTO_PATH" ]; then
        echo "Failed to find local proto file: $LOCAL_PROTO_PATH"
        ret_val=$FILE_NAME
        exit 1
    fi

    cp "$LOCAL_PROTO_PATH" "${FILE_PATH}/${FILE_NAME}.proto"

    if [ ! -e "${FILE_PATH}/${FILE_NAME}.proto" ]; then
        echo "Failed to copy $LOCAL_PROTO_PATH ..."
        ret_val=$FILE_NAME
        exit 1
    fi
}

generateGrpc() {
    PKG_NAME=$1
    FILE_NAME=$2
    FILE_PATH="${PROTO_PATH}/${PKG_NAME}/v1"

    python3 -m grpc_tools.protoc -I ${SRC} --python_out=${SRC} --grpc_python_out=${SRC} --mypy_out=${SRC} ${FILE_PATH}/${FILE_NAME}.proto

    if [ ! -e "${FILE_PATH}/${FILE_NAME}_pb2.py" ]; then
        echo "failed to generate proto buf $FILE_NAME"
        ret_val=$FILE_NAME
        exit 1
    fi
}

fail_trap() {
    result=$?
    if [ $result != 0 ]; then
        echo "Failed to generate gRPC interface and proto buf: $ret_val"
    fi
    cleanup
    exit $result
}

cleanup() {
    find $PROTO_PATH -type f -name '*.proto' -delete
}

generateGrpcSuccess() {
    export PYTHONPATH=`pwd`/$SRC
    echo -e "\ngRPC interface and proto buf generated successfully from local dapr repository!"
}

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
trap "fail_trap" EXIT

checkLocalDaprRepo
checkDependencies
copyFile common common
generateGrpc common common
copyFile runtime appcallback
generateGrpc runtime appcallback
copyFile runtime dapr
generateGrpc runtime dapr
cleanup

generateGrpcSuccess 
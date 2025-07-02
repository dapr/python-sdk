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

# Local Dapr repository path
LOCAL_DAPR_PATH="../../dapr"

copyLocalFile() {
    PKG_NAME=$1
    FILE_NAME=$2
    FILE_PATH="${PROTO_PATH}/${PKG_NAME}/v1"
    
    # Local proto file path
    LOCAL_PROTO_FILE="${LOCAL_DAPR_PATH}/dapr/proto/${PKG_NAME}/v1/${FILE_NAME}.proto"

    mkdir -p "${FILE_PATH}"

    echo "Copying local file $LOCAL_PROTO_FILE ..."
    
    if [ ! -e "$LOCAL_PROTO_FILE" ]; then
        echo "Local proto file not found: $LOCAL_PROTO_FILE"
        echo "Make sure the local Dapr repository is available at $LOCAL_DAPR_PATH"
        exit 1
    fi
    
    cp "$LOCAL_PROTO_FILE" "${FILE_PATH}/${FILE_NAME}.proto"

    if [ ! -e "${FILE_PATH}/${FILE_NAME}.proto" ]; then
        echo "failed to copy $LOCAL_PROTO_FILE ..."
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
    
    echo "Writing mypy to ${FILE_PATH}/${FILE_NAME}_pb2.pyi"
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
    echo -e "\ngRPC interface and proto buf generated successfully!"
}

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
trap "fail_trap" EXIT

copyLocalFile common common
generateGrpc common common
copyLocalFile runtime appcallback
generateGrpc runtime appcallback
copyLocalFile runtime dapr
generateGrpc runtime dapr
cleanup

generateGrpcSuccess


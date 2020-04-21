#!/bin/bash

# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

DAPR="dapr"
DAPR_CLIENT="daprclient"

# Path to store output
OUT_PATH="./src/dapr"

# Http request CLI
HTTP_REQUEST_CLI=curl


checkHttpRequestCLI() {
    if type "curl" > /dev/null; then
        HTTP_REQUEST_CLI=curl
    elif type "wget" > /dev/null; then
        HTTP_REQUEST_CLI=wget
    else
        echo "Either curl or wget is required"
        exit 1
    fi
}

downloadFile() {

    FILE_NAME=$1

    # URL for proto file
    PROTO_URL="https://raw.githubusercontent.com/dapr/dapr/master/pkg/proto/${FILE_NAME}/v1/${FILE_NAME}.proto"

    mkdir -p "$DAPR"

    echo "Downloading $PROTO_URL ..."
    if [ "$HTTP_REQUEST_CLI" == "curl" ]; then
        cd ${DAPR}
        curl -SsL "$PROTO_URL" -o "${FILE_NAME}.proto"
        cd ..
    else
        wget -q -P "$PROTO_URL" "${DAPR}/${FILE_NAME}.proto"
    fi

    if [ ! -e "${DAPR}/${FILE_NAME}.proto" ]; then
        echo "failed to download $PROTO_URL ..."
        exit 1
    fi
}

generateGrpc() {

    FILE_NAME=$1

    python3 -m grpc_tools.protoc -I $DAPR/ --python_out=${OUT_PATH} --grpc_python_out=${OUT_PATH} $DAPR/${FILE_NAME}.proto

    ret_val=$FILE_NAME
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
    if [ -e "${DAPR}" ]; then
        rm -rf "${DAPR}"
    fi
}

generateGrpcSuccess() {
    echo -e "\ngRPC interface and proto buf generated successfully!"
}

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
trap "fail_trap" EXIT

checkHttpRequestCLI
downloadFile $DAPR
generateGrpc $DAPR
downloadFile $DAPR_CLIENT
generateGrpc $DAPR_CLIENT
cleanup

generateGrpcSuccess


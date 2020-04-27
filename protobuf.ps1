
# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

$ErrorActionPreference = 'stop'

$common="common"
$dapr="dapr"
$daprClient="daprclient"

$protoFiles = @($common, $dapr, $daprClient)

# Path to store output
$protoPath="src\dapr\proto"

# Download proto files
foreach($protoFile in $protoFiles){
    $url = "https://raw.githubusercontent.com/dapr/dapr/master/dapr/proto/${protoFile}/v1/${protoFile}.proto"

    $filePath = "${protoPath}\${protoFile}\v1"

    # Create a directory to store proto files
    New-Item -ErrorAction Ignore -ItemType "directory" -Force -Path $filePath

    Invoke-WebRequest -Uri $url -OutFile "${filePath}\${protoFile}.proto"

    # gRPC code generation
    Invoke-Expression "python3 -m grpc_tools.protoc -I ${src} --python_out=${src} --grpc_python_out=${src} ${filePath}\${protoFile}.proto"

}

# Clean up
Write-Output "Cleaning up ..."
foreach($protoFile in $protoFiles){
    $filePath = "${protoPath}\${protoFile}\v1"
    Remove-Item ${filePath}\${protoFile}.proto -Force
}

# Success message
Write-Output "gRPC interface and proto buf generated successfully"

# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

$ErrorActionPreference = 'stop'

$dapr="dapr"
$daprClient="daprclient"

$protoFiles = @($dapr, $daprClient)

# Path to store output
$outPath="./src/dapr"

# Create a directory to store proto files
New-Item -ErrorAction Ignore -Path . -Name $dapr -ItemType "directory"

# Download proto files

foreach($protoFile in $protoFiles){
    $url = "https://raw.githubusercontent.com/dapr/dapr/master/pkg/proto/${protoFile}/v1/${protoFile}.proto"

    Invoke-WebRequest -Uri $url -OutFile "${dapr}\${protoFile}.proto"

    # gRPC code generation
    Invoke-Expression "python3 -m grpc_tools.protoc -I ${dapr} --python_out=${outPath} --grpc_python_out=${outPath} ${dapr}/${protoFile}.proto"
}

# Clean up
Write-Output "Cleaning up ..."
Remove-Item $dapr -Recurse -Force

# Success message
Write-Output "gRPC interface and proto buf generated successfully"
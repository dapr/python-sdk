
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
$outPath=".\src"
$commonOutPath=".\pkg\proto\common\v1"

# Create a directory to store proto files
New-Item -ErrorAction Ignore -Path . -Name $dapr -ItemType "directory"

# Download proto files
foreach($protoFile in $protoFiles){
    $url = "https://raw.githubusercontent.com/dapr/dapr/master/pkg/proto/${protoFile}/v1/${protoFile}.proto"

    Invoke-WebRequest -Uri $url -OutFile "${dapr}\${protoFile}.proto"

    # gRPC code generation
    Invoke-Expression "python3 -m grpc_tools.protoc -I . --python_out=${outPath} --grpc_python_out=${outPath} ${dapr}\${protoFile}.proto"

    if($protoFile -eq $common){
        New-Item -ErrorAction Ignore -ItemType "directory" -Force -Path $commonOutPath

        Move-Item -Path "${outPath}\${dapr}\${protoFile}*" -Destination "$commonOutPath"
    }

}

# Clean up
Write-Output "Cleaning up ..."
Remove-Item $dapr -Recurse -Force
Remove-Item ${commonOutPath}\${common}.proto -Force

# Success message
Write-Output "gRPC interface and proto buf generated successfully"
// Storage account + blob container holding the source documents this
// pipeline ingests. Public blob access is disabled -- the ingestion identity
// reads through Microsoft Entra ID (Storage Blob Data Reader; see
// docs/rag/azure-rbac.md), never a connection string or SAS token.

@description('Azure region.')
param location string

@description('Globally-unique storage account name (lowercase alphanumeric, <=24 chars).')
param storageAccountName string

@description('Blob container name for source documents.')
param blobContainerName string

@description('Tags applied to the storage account.')
param tags object = {}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource sourceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: blobContainerName
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output containerName string = sourceContainer.name

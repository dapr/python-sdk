// Azure OpenAI (Cognitive Services) account with two model deployments: an
// embeddings deployment (ingestion side) and a chat/completions deployment
// (query side). Both live on one account since Azure OpenAI RBAC roles are
// account-scoped, not deployment-scoped -- see docs/rag/azure-rbac.md for
// the consequence of that (both workload identities end up with the same
// "Cognitive Services OpenAI User" role on this account).

@description('Azure region. Model/version availability varies by region -- verify before deploying.')
param location string

@description('Globally-unique Azure OpenAI account name.')
param openAiAccountName string

@description('Azure OpenAI account SKU.')
param skuName string = 'S0'

@description('Embeddings model name, e.g. text-embedding-3-small.')
param embeddingModelName string

@description('Embeddings model version.')
param embeddingModelVersion string

@description('Embeddings deployment name.')
param embeddingDeploymentName string

@description('Embeddings deployment capacity (capacity units).')
param embeddingCapacity int

@description('Chat model name, e.g. gpt-4o.')
param chatModelName string

@description('Chat model version.')
param chatModelVersion string

@description('Chat deployment name.')
param chatDeploymentName string

@description('Chat deployment capacity (capacity units).')
param chatCapacity int

@description('Deployment SKU shared by both deployments (e.g. GlobalStandard, Standard).')
param deploymentSkuName string = 'GlobalStandard'

@description('Tags applied to the account.')
param tags object = {}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiAccountName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  kind: 'OpenAI'
  properties: {
    customSubDomainName: openAiAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: embeddingDeploymentName
  sku: {
    name: deploymentSkuName
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: chatDeploymentName
  sku: {
    name: deploymentSkuName
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
  // Azure OpenAI serializes deployment operations against one account --
  // creating both deployments "in parallel" (Bicep's default behavior for
  // sibling resources with no data dependency) can 409. This dependsOn
  // forces them to run one after the other.
  dependsOn: [
    embeddingDeployment
  ]
}

output openAiAccountId string = openAiAccount.id
output openAiAccountName string = openAiAccount.name
output openAiEndpoint string = openAiAccount.properties.endpoint
output embeddingDeploymentName string = embeddingDeployment.name
output chatDeploymentName string = chatDeployment.name

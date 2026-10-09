// Every role and access-policy assignment for the two workload identities,
// centralized here so it can be reviewed as a single unit against
// docs/rag/azure-rbac.md's role table. Nothing in this file grants a
// subscription- or resource-group-scoped role (e.g. Owner/Contributor) --
// every assignment is scoped to the one resource that needs it.
//
// Built-in role names and IDs below were verified against Microsoft Learn's
// built-in-roles reference and each service's own RBAC documentation on
// 2026-09-10 (see docs/rag/azure-rbac.md for the exact pages and citations).

@description('Principal (object) ID of the ingestion workload managed identity.')
param ingestionPrincipalId string

@description('Principal (object) ID of the query workload managed identity.')
param queryPrincipalId string

@description('Storage account name (source documents).')
param storageAccountName string

@description('Service Bus namespace name.')
param serviceBusNamespaceName string

@description('Service Bus topic name.')
param serviceBusTopicName string

@description('Service Bus subscription name the ingestion workload consumes from.')
param serviceBusSubscriptionName string

@description('Azure AI Search service name.')
param searchServiceName string

@description('Azure OpenAI account name.')
param openAiAccountName string

@description('Azure Cache for Redis name.')
param redisName string

@description('Whether the optional Key Vault was deployed; gates the Key Vault Secrets User assignments below.')
param deploySecretStore bool = false

@description('Key Vault name. Required only when deploySecretStore is true.')
param keyVaultName string = ''

// --- Built-in role definition IDs -- see docs/rag/azure-rbac.md for the verified name/description behind each. ---
var roleIdStorageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var roleIdServiceBusDataReceiver = '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
var roleIdSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var roleIdSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleIdSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var roleIdCognitiveServicesOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61ae'
var roleIdKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource sbNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' existing = {
  name: serviceBusNamespaceName
}

resource sbTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' existing = {
  parent: sbNamespace
  name: serviceBusTopicName
}

resource sbSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' existing = {
  parent: sbTopic
  name: serviceBusSubscriptionName
}

resource searchService 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchServiceName
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource redisCache 'Microsoft.Cache/redis@2024-11-01' existing = {
  name: redisName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (deploySecretStore) {
  name: keyVaultName
}

// ============ Ingestion identity ============
// Reads source blobs, receives the Service Bus trigger, creates/manages
// Search indexes and the alias, writes Search documents, and calls the
// embeddings deployment. This is also "the Service Bus consumer identity":
// it must not be able to do anything beyond receiving messages (no Send,
// no Manage) on the namespace.

resource ingestionBlobRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, ingestionPrincipalId, roleIdStorageBlobDataReader)
  scope: storageAccount
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdStorageBlobDataReader)
  }
}

resource ingestionServiceBusReceive 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sbSubscription.id, ingestionPrincipalId, roleIdServiceBusDataReceiver)
  scope: sbSubscription
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdServiceBusDataReceiver)
  }
}

resource ingestionSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, ingestionPrincipalId, roleIdSearchServiceContributor)
  scope: searchService
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdSearchServiceContributor)
  }
}

resource ingestionSearchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, ingestionPrincipalId, roleIdSearchIndexDataContributor)
  scope: searchService
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdSearchIndexDataContributor)
  }
}

resource ingestionOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, ingestionPrincipalId, roleIdCognitiveServicesOpenAiUser)
  scope: openAiAccount
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdCognitiveServicesOpenAiUser)
  }
}

// Redis data-plane access uses its own access-policy-assignment concept
// (not Microsoft.Authorization/roleAssignments). "Data Owner" gives
// ingestion the read-write access Dapr Workflow's actor state store needs.
resource ingestionRedisAccess 'Microsoft.Cache/redis/accessPolicyAssignments@2024-11-01' = {
  parent: redisCache
  name: 'ingestion-identity'
  properties: {
    accessPolicyName: 'Data Owner'
    objectId: ingestionPrincipalId
    objectIdAlias: 'ingestionWorkloadIdentity'
  }
}

resource ingestionKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deploySecretStore) {
  name: guid(keyVaultName, ingestionPrincipalId, roleIdKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdKeyVaultSecretsUser)
  }
}

// ============ Query identity ============
// Strictly narrower than ingestion: read-only Search access, inference-only
// OpenAI access, read-only Redis access to resolve the active version
// pointer. Must NOT be able to create/delete indexes, switch the alias,
// write documents, touch Storage, or touch Service Bus.

resource querySearchIndexDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, queryPrincipalId, roleIdSearchIndexDataReader)
  scope: searchService
  properties: {
    principalId: queryPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdSearchIndexDataReader)
  }
}

resource queryOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, queryPrincipalId, roleIdCognitiveServicesOpenAiUser)
  scope: openAiAccount
  properties: {
    principalId: queryPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdCognitiveServicesOpenAiUser)
  }
}

resource queryRedisAccess 'Microsoft.Cache/redis/accessPolicyAssignments@2024-11-01' = {
  parent: redisCache
  name: 'query-identity'
  properties: {
    accessPolicyName: 'Data Reader'
    objectId: queryPrincipalId
    objectIdAlias: 'queryWorkloadIdentity'
  }
}

resource queryKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deploySecretStore) {
  name: guid(keyVaultName, queryPrincipalId, roleIdKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    principalId: queryPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdKeyVaultSecretsUser)
  }
}

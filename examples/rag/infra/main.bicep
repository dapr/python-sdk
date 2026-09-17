// Azure infrastructure for the dapr.ext.rag example: a durable RAG ingestion
// pipeline (DurableRAGPipeline) running on Dapr Workflow, with an Azure AI
// Search-backed vector store, Azure OpenAI for embeddings/chat, Azure Cache
// for Redis as the Dapr Workflow actor state store, and an Event Grid ->
// Service Bus -> Dapr pub/sub trigger path from Blob Storage.
//
// STARTING POINT, NOT A VALIDATED TEMPLATE. This file was authored without
// access to an Azure subscription to deploy or test against -- there is no
// substitute for reviewing every resource, SKU, and role assignment below
// before using it against a real subscription. See infra/README.md for the
// full disclaimer, prerequisites, and deployment command.
//
// Naming: every globally-unique resource name is derived from `namePrefix`
// and `uniqueString(resourceGroup().id)` -- nothing here hard-codes a name,
// region, subscription ID, or tenant ID.
//
// See docs/rag/azure-rbac.md for the two identities this template provisions
// (ingestion vs. query) and exactly which role each role assignment below
// corresponds to.

targetScope = 'resourceGroup'

@description('Short prefix used to build resource names. Keep it short and lowercase-alphanumeric: it feeds into length-constrained names (storage account, Key Vault).')
@maxLength(12)
param namePrefix string = 'rag'

@description('Azure region for all resources. Defaults to the location of the target resource group.')
param location string = resourceGroup().location

@description('Tags applied to every resource this template creates.')
param tags object = {
  sample: 'dapr-rag-pipeline'
}

@description('Name of the blob container that holds source documents.')
param blobContainerName string = 'source-documents'

@description('Service Bus topic that receives Blob Storage change notifications relayed by Event Grid.')
param serviceBusTopicName string = 'blob-events'

@description('Service Bus subscription the ingestion workload consumes from via Dapr pub/sub.')
param serviceBusSubscriptionName string = 'rag-ingestion'

@description('Service Bus namespace SKU. Topics require Standard or Premium -- Basic tier does not support topics/subscriptions at all.')
@allowed([
  'Standard'
  'Premium'
])
param serviceBusSkuName string = 'Standard'

@description('Attempt to provision the Event Grid system topic + event subscription that relays Blob Storage change events to the Service Bus topic. When false, wire this manually -- see infra/README.md for the equivalent az cli steps.')
param deployEventGridSubscription bool = true

@description('Azure AI Search SKU. Free supports hybrid/vector search but has tight per-service limits (3 indexes, 50 MB storage) and no semantic ranking. Basic is the practical minimum for this sample: it supports semantic ranking (used to re-rank hybrid results) and comfortably holds the base + in-progress-version indexes this pipeline creates during a rebuild.')
@allowed([
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param searchSkuName string = 'basic'

@description('Base name for the versioned physical indexes and the stable alias this pipeline manages, e.g. "company-knowledge" -> indexes "company-knowledge-2026-09", alias "company-knowledge-active". Passed straight through to AzureAISearchVectorStore(index_base_name=...).')
param searchIndexBaseName string = 'company-knowledge'

@description('Azure OpenAI account SKU. S0 is the standard (only) SKU for Azure OpenAI accounts today.')
param openAiSkuName string = 'S0'

@description('Embeddings model to deploy. Model/version availability varies by region and subscription -- verify with `az cognitiveservices account list-models` before relying on this default.')
param embeddingModelName string = 'text-embedding-3-small'

@description('Embeddings model version.')
param embeddingModelVersion string = '1'

@description('Provisioned throughput for the embeddings deployment (capacity units; 1 unit = 1K TPM for Standard/GlobalStandard SKUs).')
param embeddingDeploymentCapacity int = 30

@description('Chat/completions model deployed for query-time, grounded answer generation. Model/version availability varies by region and subscription.')
param chatModelName string = 'gpt-4o'

@description('Chat model version.')
param chatModelVersion string = '2024-11-20'

@description('Provisioned throughput for the chat deployment.')
param chatDeploymentCapacity int = 10

@description('Deployment SKU shared by both model deployments. GlobalStandard has the broadest quota availability; fall back to Standard if GlobalStandard is not offered for a model/region combination in your subscription.')
param openAiDeploymentSkuName string = 'GlobalStandard'

@description('Azure Cache for Redis SKU name backing the Dapr Workflow actor state store.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param redisSkuName string = 'Basic'

@description('Redis SKU family: C for Basic/Standard, P for Premium.')
param redisSkuFamily string = 'C'

@description('Redis SKU capacity/size within the family (0-6 for Basic/Standard family C).')
param redisSkuCapacity int = 1

@description('Deploy an optional Azure Key Vault secret store. The recommended path needs no secrets at all (pure managed/workload identity) -- only enable this if a deployment intentionally keeps a dev-only credential (e.g. a fallback API key) outside of identity-based auth.')
param deploySecretStore bool = false

var uniqueSuffix = uniqueString(resourceGroup().id, namePrefix)
var storageAccountName = take(toLower('${namePrefix}st${uniqueSuffix}'), 24)
var serviceBusNamespaceName = '${namePrefix}-sb-${uniqueSuffix}'
var searchServiceName = '${namePrefix}-search-${uniqueSuffix}'
var openAiAccountName = '${namePrefix}-aoai-${uniqueSuffix}'
var redisName = '${namePrefix}-redis-${uniqueSuffix}'
var keyVaultName = take('${namePrefix}-kv-${uniqueSuffix}', 24)
var logAnalyticsName = '${namePrefix}-logs-${uniqueSuffix}'
var appInsightsName = '${namePrefix}-appi-${uniqueSuffix}'
var ingestionIdentityName = '${namePrefix}-ingestion-id'
var queryIdentityName = '${namePrefix}-query-id'
var embeddingDeploymentName = 'embedding'
var chatDeploymentName = 'chat'
var searchAliasName = '${searchIndexBaseName}-active'
// Free tier cannot run the semantic ranker at all; every paid tier can.
var semanticSearchSetting = searchSkuName == 'free' ? 'disabled' : 'standard'

module identities 'modules/identity.bicep' = {
  name: 'identities'
  params: {
    location: location
    ingestionIdentityName: ingestionIdentityName
    queryIdentityName: queryIdentityName
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: storageAccountName
    blobContainerName: blobContainerName
    tags: tags
  }
}

module serviceBus 'modules/servicebus.bicep' = {
  name: 'serviceBus'
  params: {
    location: location
    serviceBusNamespaceName: serviceBusNamespaceName
    skuName: serviceBusSkuName
    topicName: serviceBusTopicName
    subscriptionName: serviceBusSubscriptionName
    tags: tags
  }
}

// Blob Storage -> Event Grid -> this Service Bus topic. See the module for
// the identity-based delivery wiring and infra/README.md for the manual
// az cli fallback if you set deployEventGridSubscription to false.
module eventGrid 'modules/eventgrid.bicep' = if (deployEventGridSubscription) {
  name: 'eventGrid'
  params: {
    location: location
    storageAccountId: storage.outputs.storageAccountId
    storageAccountName: storage.outputs.storageAccountName
    serviceBusNamespaceName: serviceBus.outputs.namespaceName
    serviceBusTopicName: serviceBus.outputs.topicName
    serviceBusTopicId: serviceBus.outputs.topicId
    tags: tags
  }
}

module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: location
    searchServiceName: searchServiceName
    skuName: searchSkuName
    semanticSearchTier: semanticSearchSetting
    tags: tags
  }
}

module openAi 'modules/openai.bicep' = {
  name: 'openAi'
  params: {
    location: location
    openAiAccountName: openAiAccountName
    skuName: openAiSkuName
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingDeploymentName: embeddingDeploymentName
    embeddingCapacity: embeddingDeploymentCapacity
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    chatDeploymentName: chatDeploymentName
    chatCapacity: chatDeploymentCapacity
    deploymentSkuName: openAiDeploymentSkuName
    tags: tags
  }
}

// NOTE (flagged for review, see infra/README.md): Microsoft has announced a
// retirement timeline for Azure Cache for Redis across all SKUs in favor of
// "Azure Managed Redis". This module still targets Microsoft.Cache/redis
// because that is what the Dapr Redis state store component documents and
// what this sample's Dapr component YAML (examples/rag/components/azure/
// workflow-statestore.yaml) is written against. Re-evaluate against Azure
// Managed Redis before using this in a long-lived deployment.
module redis 'modules/redis.bicep' = {
  name: 'redis'
  params: {
    location: location
    redisName: redisName
    skuName: redisSkuName
    skuFamily: redisSkuFamily
    skuCapacity: redisSkuCapacity
    tags: tags
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    tags: tags
  }
}

module keyVault 'modules/keyvault.bicep' = if (deploySecretStore) {
  name: 'keyVault'
  params: {
    deploy: deploySecretStore
    location: location
    keyVaultName: keyVaultName
    tags: tags
  }
}

// Centralizes every role/access-policy assignment for both workload
// identities in one auditable place -- cross-reference against the table in
// docs/rag/azure-rbac.md.
module rbac 'modules/rbac.bicep' = {
  name: 'rbac'
  params: {
    ingestionPrincipalId: identities.outputs.ingestionPrincipalId
    queryPrincipalId: identities.outputs.queryPrincipalId
    storageAccountName: storage.outputs.storageAccountName
    serviceBusNamespaceName: serviceBus.outputs.namespaceName
    serviceBusTopicName: serviceBus.outputs.topicName
    serviceBusSubscriptionName: serviceBus.outputs.subscriptionName
    searchServiceName: search.outputs.searchServiceName
    openAiAccountName: openAi.outputs.openAiAccountName
    redisName: redis.outputs.redisName
    deploySecretStore: deploySecretStore
    keyVaultName: keyVault.?outputs.?keyVaultName ?? ''
  }
}

@description('Storage account name backing the source-documents container.')
output storageAccountName string = storage.outputs.storageAccountName

@description('Blob endpoint for the storage account.')
output blobEndpoint string = storage.outputs.blobEndpoint

@description('Source-documents blob container name.')
output sourceContainerName string = storage.outputs.containerName

@description('Service Bus namespace fully-qualified domain name -- fills the namespaceName field of the pubsub component.')
output serviceBusNamespaceHostName string = '${serviceBus.outputs.namespaceName}.servicebus.windows.net'

@description('Service Bus topic that receives Blob Storage change events.')
output serviceBusTopicName string = serviceBus.outputs.topicName

@description('Service Bus subscription the ingestion workload consumes from.')
output serviceBusSubscriptionName string = serviceBus.outputs.subscriptionName

@description('Azure AI Search endpoint -- AzureAISearchVectorStore(endpoint=...).')
output searchEndpoint string = search.outputs.searchEndpoint

@description('Base name for versioned physical indexes -- AzureAISearchVectorStore(index_base_name=...).')
output searchIndexBaseName string = searchIndexBaseName

@description('Stable alias name the query path reads through -- AzureAISearchVectorStore(alias_name=...).')
output searchAliasName string = searchAliasName

@description('Azure OpenAI endpoint -- AzureOpenAIEmbedder(endpoint=...) and AzureOpenAIChatClient(endpoint=...).')
output openAiEndpoint string = openAi.outputs.openAiEndpoint

@description('Embeddings deployment name -- AzureOpenAIEmbedder(deployment=...).')
output openAiEmbeddingDeploymentName string = openAi.outputs.embeddingDeploymentName

@description('Chat deployment name -- AzureOpenAIChatClient(deployment=...).')
output openAiChatDeploymentName string = openAi.outputs.chatDeploymentName

@description('Redis host name for the redisHost field of the Dapr state store component (pair with redisSslPort for the "host:port" form).')
output redisHostName string = redis.outputs.redisHostName

@description('Redis TLS port, required alongside redisHostName for useEntraID / enableTLS.')
output redisSslPort int = redis.outputs.redisSslPort

@description('Ingestion workload managed identity: client ID (Dapr component YAML azureClientId).')
output ingestionIdentityClientId string = identities.outputs.ingestionClientId

@description('Ingestion workload managed identity: full resource ID (for workload-identity federation or VM/container host identity association).')
output ingestionIdentityResourceId string = identities.outputs.ingestionIdentityId

@description('Query workload managed identity: client ID.')
output queryIdentityClientId string = identities.outputs.queryClientId

@description('Query workload managed identity: full resource ID.')
output queryIdentityResourceId string = identities.outputs.queryIdentityId

@description('Application Insights connection string for OpenTelemetry export -- see docs/rag/observability.md.')
output appInsightsConnectionString string = monitoring.outputs.connectionString

@description('Log Analytics workspace resource ID backing Application Insights.')
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId

@description('Key Vault name. Empty string unless deploySecretStore is true.')
output keyVaultName string = keyVault.?outputs.?keyVaultName ?? ''

@description('Key Vault URI. Empty string unless deploySecretStore is true.')
output keyVaultUri string = keyVault.?outputs.?keyVaultUri ?? ''

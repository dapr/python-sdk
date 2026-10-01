// Azure AI Search service. This module only provisions the *service* --
// DurableRAGPipeline itself creates one physical index per pipeline version
// (via AzureAISearchVectorStore) and manages the stable alias at runtime, so
// no index or alias resource is declared here.

@description('Azure region.')
param location string

@description('Globally-unique search service name.')
param searchServiceName string

@description('Search service SKU.')
param skuName string = 'basic'

@description('Semantic ranker tier: "standard" on paid tiers, "disabled" on Free (which cannot run the semantic ranker at all).')
param semanticSearchTier string = 'standard'

@description('Tags applied to the search service.')
param tags object = {}

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: semanticSearchTier
    // "Both" mode: keeps key-based auth available (e.g. for the portal's
    // Search Explorer while validating this deployment) alongside Microsoft
    // Entra ID / RBAC, which is what the ingestion and query identities
    // actually use (see modules/rbac.bicep). Tighten to disableLocalAuth:
    // true once RBAC access is confirmed working, for a fully keyless
    // service -- see infra/README.md.
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    disableLocalAuth: false
  }
}

output searchServiceId string = searchService.id
output searchServiceName string = searchService.name
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'

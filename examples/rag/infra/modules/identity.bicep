// Two user-assigned managed identities: one for the ingestion workload
// (Dapr Workflow worker: reads blobs, consumes Service Bus, writes/activates
// Search indexes, calls the embeddings deployment) and one for the query
// workload (RAG query API: reads Search only, calls the chat deployment).
// Splitting these in two -- rather than one shared identity -- is what makes
// the least-privilege role assignments in modules/rbac.bicep possible; see
// docs/rag/azure-rbac.md for exactly what each may and may not do.

@description('Azure region for both identities.')
param location string

@description('Name of the managed identity for the ingestion workload.')
param ingestionIdentityName string

@description('Name of the managed identity for the query workload.')
param queryIdentityName string

@description('Tags applied to both identities.')
param tags object = {}

resource ingestionIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: ingestionIdentityName
  location: location
  tags: tags
}

resource queryIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: queryIdentityName
  location: location
  tags: tags
}

output ingestionIdentityId string = ingestionIdentity.id
output ingestionPrincipalId string = ingestionIdentity.properties.principalId
output ingestionClientId string = ingestionIdentity.properties.clientId
output queryIdentityId string = queryIdentity.id
output queryPrincipalId string = queryIdentity.properties.principalId
output queryClientId string = queryIdentity.properties.clientId

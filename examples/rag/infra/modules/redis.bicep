// Azure Cache for Redis, used as the Dapr actor state store backing both
// Dapr Workflow's own orchestration state and this pipeline's idempotency
// records (see examples/rag/components/azure/workflow-statestore.yaml).
//
// FLAGGED FOR REVIEW: Microsoft has announced a retirement timeline for
// Azure Cache for Redis across all SKUs (Basic/Standard/Premium), directing
// new workloads to "Azure Managed Redis" instead
// (https://learn.microsoft.com/azure/azure-cache-for-redis/cache-azure-active-directory-for-authentication,
// fetched 2026-09-10). This module still targets Microsoft.Cache/redis
// because that is the resource type Dapr's Redis state store component and
// this sample's component YAML are documented against, and because this
// template cannot be deployed or tested in this environment -- re-evaluate
// against Azure Managed Redis (or Cosmos DB, see docs/rag/azure-rbac.md and
// the pipeline's own state-store docs) before committing to this for a
// long-lived deployment.
//
// `redisConfiguration['aad-enabled']` turns on Microsoft Entra ID
// authentication; modules/rbac.bicep grants each workload identity a Redis
// access-policy assignment ("Data Owner" for ingestion, "Data Reader" for
// query) rather than a generic Azure role, since Redis data-plane access
// uses its own access-policy concept, not Microsoft.Authorization
// roleAssignments.

@description('Azure region.')
param location string

@description('Globally-unique cache name.')
param redisName string

@description('Redis SKU name.')
param skuName string = 'Basic'

@description('Redis SKU family: C for Basic/Standard, P for Premium.')
param skuFamily string = 'C'

@description('Redis SKU capacity within the family.')
param skuCapacity int = 1

@description('Tags applied to the cache.')
param tags object = {}

resource redisCache 'Microsoft.Cache/redis@2024-11-01' = {
  name: redisName
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      'aad-enabled': 'true'
    }
  }
}

output redisId string = redisCache.id
output redisName string = redisCache.name
output redisHostName string = redisCache.properties.hostName
output redisSslPort int = redisCache.properties.sslPort

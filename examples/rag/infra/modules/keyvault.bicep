// Optional Azure Key Vault, only created when the caller opts into the
// non-default secrets path (deploySecretStore = true). The recommended
// deployment of this sample needs no secrets at all: every component
// authenticates via the ingestion/query managed identities.
//
// Uses Azure RBAC for data-plane authorization (enableRbacAuthorization:
// true), not the legacy vault access-policy model, so access is granted via
// modules/rbac.bicep's "Key Vault Secrets User" role assignments.

@description('Set to true to create the vault; false deploys nothing from this module.')
param deploy bool = false

@description('Azure region.')
param location string

@description('Globally-unique Key Vault name (<=24 chars).')
param keyVaultName string

@description('Microsoft Entra tenant ID for the vault. Defaults to the tenant of the current deployment -- never hard-code a tenant ID.')
param tenantId string = subscription().tenantId

@description('Tags applied to the vault.')
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (deploy) {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
  }
}

output keyVaultName string = keyVault.?name ?? ''
output keyVaultUri string = keyVault.?properties.?vaultUri ?? ''

# RAG pipeline infrastructure (Bicep)

Bicep templates that provision the Azure resources for the flagship, Azure-native deployment of
`DurableRAGPipeline`:

```
Azure Blob Storage
    -> Event Grid -> Azure Service Bus -> Dapr pub/sub -> Dapr Workflow
        -> download, parse, chunk (workflow activities)
        -> Azure OpenAI embeddings (workflow activities)
        -> write to a version-specific Azure AI Search index (workflow activities)
        -> validate the new index, then atomically switch the Azure AI Search alias
    -> RAG query API
        -> Azure AI Search hybrid retrieval, queried via the alias
        -> Azure OpenAI chat completion for a grounded, cited answer
```

## Status: starting point, not a validated template

**This Bicep was authored, and reviewed with the standalone Bicep CLI (`bicep build` / `bicep
lint`, both clean), in an environment with no Azure subscription available.** It has not been
deployed against a real subscription, and no `az deployment group what-if`/`create` has been run
against it. Treat it as a reviewed starting point, not production-ready infrastructure:

- Re-check every SKU, capacity, and default value against your own quota, region availability,
  and cost constraints before deploying.
- Re-check the two flagged items below before relying on this in anything long-lived.
- Have someone who owns your subscription's security posture review the RBAC design in
  [`../../../docs/rag/azure-rbac.md`](../../../docs/rag/azure-rbac.md) before granting it access to
  real data.

### Flagged for review

1. **Azure Cache for Redis retirement.** Microsoft has announced a retirement timeline for Azure
   Cache for Redis across all SKUs, directing new workloads to "Azure Managed Redis" instead (see
   the retirement notice on [Microsoft Learn's Entra ID authentication
   page](https://learn.microsoft.com/azure/azure-cache-for-redis/cache-azure-active-directory-for-authentication),
   fetched 2026-09-10). `modules/redis.bicep` still provisions `Microsoft.Cache/redis` because
   that is what the Dapr Redis state store component and this sample's component YAML
   (`../components/azure/workflow-statestore.yaml`) are documented against. Re-evaluate against
   Azure Managed Redis, or against the Cosmos DB alternative mentioned in the RBAC doc, before
   committing to this for anything long-lived.
2. **Redis Microsoft Entra ID wiring is the least independently-verified part of this template.**
   The `redisConfiguration['aad-enabled']` property and the `Microsoft.Cache/redis/accessPolicyAssignments`
   sub-resource (with built-in access policy names `Data Owner` / `Data Reader`) reflect the
   product behavior described in Microsoft's own Redis Entra ID documentation, but the exact ARM
   property/resource shape was not independently confirmed against the ARM template reference in
   this session. It compiles cleanly with the Bicep CLI, which validates property names against
   the resource type's schema, but a schema-valid template can still behave differently than
   intended at runtime. Confirm end-to-end (enable Entra auth, assign an access policy, connect
   with `useEntraID: "true"`) against a real cache before depending on it.

## Prerequisites

- An Azure subscription and a resource group to deploy into.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), signed in:
  ```sh
  az login
  az account set --subscription <subscription-id-or-name>
  ```
- Bicep tooling. The Azure CLI can install/update it for you:
  ```sh
  az bicep install
  az bicep upgrade
  ```
- Quota for an Azure OpenAI resource with the embeddings and chat models/versions you intend to
  deploy, in your target region. Azure OpenAI model availability varies by region and
  subscription -- check with:
  ```sh
  az cognitiveservices account list-models \
    --location <region> \
    --query "[].{model:name, version:version}" \
    -o table
  ```
  (This requires an existing Cognitive Services account in that region to query against, or use
  the [Azure AI Foundry model catalog](https://ai.azure.com) to check regional availability before
  deploying.)

## Deploy

```sh
az group create --name <resource-group-name> --location <region>

az deployment group create \
  --resource-group <resource-group-name> \
  --template-file main.bicep \
  --parameters namePrefix=rag \
  --parameters embeddingModelVersion=<verify-current-version> \
  --parameters chatModelVersion=<verify-current-version>
```

Every parameter has a default (see `main.bicep`'s `@description` decorators); override only what
you need to. Common overrides:

```sh
az deployment group create \
  --resource-group <resource-group-name> \
  --template-file main.bicep \
  --parameters \
      namePrefix=myrag \
      location=eastus2 \
      searchSkuName=standard \
      embeddingModelName=text-embedding-3-small \
      embeddingModelVersion=1 \
      chatModelName=gpt-4o \
      chatModelVersion=2024-11-20 \
      deploySecretStore=false
```

After a successful deployment, read the outputs back out to fill in the Python config surface and
the Dapr component YAMLs:

```sh
az deployment group show \
  --resource-group <resource-group-name> \
  --name main \
  --query properties.outputs
```

## What gets created

| Resource | Purpose |
|---|---|
| Storage account + blob container | Source documents the pipeline ingests |
| Service Bus namespace + topic + subscription | Relays Blob Storage change events to Dapr pub/sub |
| Event Grid system topic + event subscription (optional, `deployEventGridSubscription`) | Wires Blob Storage `BlobCreated`/`BlobDeleted` events to the Service Bus topic, using the system topic's own managed identity to deliver |
| Azure AI Search service | Vector store; `DurableRAGPipeline` creates the versioned indexes and alias at runtime, not this template |
| Azure OpenAI account + 2 deployments | One embeddings deployment, one chat deployment |
| Azure Cache for Redis | Dapr Workflow actor state store + this pipeline's idempotency records (see the retirement note above) |
| 2 user-assigned managed identities | Ingestion workload and query workload, least-privilege (see `docs/rag/azure-rbac.md`) |
| Role/access-policy assignments | Wires each identity to exactly the resources it needs, scoped per-resource (never subscription- or resource-group-scoped) |
| Azure Key Vault (optional, `deploySecretStore`) | Only if a deployment intentionally keeps a dev-only secret outside of managed identity |
| Log Analytics workspace + Application Insights | OpenTelemetry destination (see `docs/rag/observability.md`) |

## Manual step: Event Grid, if `deployEventGridSubscription=false`

If you disable the Event Grid module (or it fails to deploy and you want to unblock the rest of
the stack), wire the same thing manually once the storage account and Service Bus topic exist:

```sh
az eventgrid system-topic create \
  --name <storage-account-name>-events \
  --resource-group <resource-group-name> \
  --location <region> \
  --topic-type Microsoft.Storage.StorageAccounts \
  --source /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-account-name> \
  --mi-system-assigned

az eventgrid system-topic event-subscription create \
  --name blob-to-servicebus \
  --system-topic-name <storage-account-name>-events \
  --resource-group <resource-group-name> \
  --endpoint-type servicebustopic \
  --endpoint /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ServiceBus/namespaces/<sb-namespace>/topics/<sb-topic> \
  --included-event-types Microsoft.Storage.BlobCreated Microsoft.Storage.BlobDeleted \
  --delivery-identity SystemAssigned

# The system topic's identity needs to send to the destination topic:
az role assignment create \
  --assignee-object-id <system-topic-principal-id> \
  --assignee-principal-type ServicePrincipal \
  --role "Azure Service Bus Data Sender" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ServiceBus/namespaces/<sb-namespace>/topics/<sb-topic>
```

## File layout

```
infra/
├── main.bicep              # Parameters, module wiring, outputs
├── modules/
│   ├── identity.bicep      # Ingestion + query user-assigned managed identities
│   ├── storage.bicep       # Storage account + blob container
│   ├── servicebus.bicep    # Namespace + topic + subscription
│   ├── eventgrid.bicep     # System topic + event subscription (Blob -> Service Bus)
│   ├── search.bicep        # Azure AI Search service
│   ├── openai.bicep        # Azure OpenAI account + embeddings/chat deployments
│   ├── redis.bicep         # Azure Cache for Redis (Dapr actor state store)
│   ├── keyvault.bicep      # Optional secret store
│   ├── monitoring.bicep    # Log Analytics + Application Insights
│   └── rbac.bicep          # Every role/access-policy assignment, centralized for review
└── README.md
```

## Cleaning up

```sh
az group delete --name <resource-group-name> --yes --no-wait
```

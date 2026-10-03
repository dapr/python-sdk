# Azure RBAC for the RAG pipeline

This document lists the exact Azure role assignments the Azure-native deployment of
`DurableRAGPipeline` needs, organized around the two identities
[`examples/rag/infra`](../../examples/rag/infra) provisions: an **ingestion** identity (the Dapr
Workflow worker) and a **query** identity (the RAG query API). It is the reference the Bicep's
[`modules/rbac.bicep`](../../examples/rag/infra/modules/rbac.bicep) was written against, and should
be reviewed by whoever owns your subscription's security posture before you grant either identity
access to real data.

**Verification note.** Every built-in role name below was checked against Microsoft Learn's
built-in-roles reference and each service's own RBAC documentation on **2026-09-10**, rather than
recalled from memory -- role names and casing change, and this doc is meant to be read by someone
doing a real deployment. The specific pages are cited under each role. If you are reading this much
later than that date, re-check the citations: role names occasionally change or gain
successors.

## The two identities

| Identity | Runs | Needs to |
|---|---|---|
| **Ingestion** | Dapr Workflow worker (the pipeline's activities: discover, download, parse, chunk, embed, write index, validate, activate) | Read source blobs, receive the Service Bus trigger, create/manage Search indexes and switch the alias, write Search documents, call the embeddings deployment, read+write the Redis-backed workflow state store |
| **Query** | RAG query API | Query Search documents (read-only), call the chat deployment, read the Redis-backed active-version pointer (read-only) |

The query identity is deliberately a strict subset of the ingestion identity's access. It must
**not** be able to:

- Create, delete, or reconfigure any Azure AI Search index.
- Switch the Azure AI Search alias.
- Write, update, or delete any Azure AI Search document.
- Read source blobs, or do anything with Service Bus.
- Write to the Redis-backed state store.

The ingestion identity is also, in effect, "the Service Bus consumer identity" (it is the one
workload that reads pipeline-trigger messages). It must not be able to do anything on Service Bus
beyond receiving messages from its one subscription -- no `Send`, no namespace management, no
access to other topics/subscriptions in the namespace.

**Scope discipline.** Every role assignment below is scoped to the one resource (or, for Service
Bus, the one subscription entity) that needs it. Avoid subscription-level or resource-group-level
role assignments (especially `Owner`/`Contributor` at subscription scope) for either identity --
they would grant far more than either workload needs, and would make the table below meaningless
as a security boundary.

## Role assignments

| # | Permission | Identity | Role | Scope |
|---|---|---|---|---|
| 1 | Read blobs from the source container | Ingestion | `Storage Blob Data Reader` | Storage account (or the container, for tighter scoping) |
| 2 | Receive messages from the Service Bus subscription | Ingestion | `Azure Service Bus Data Receiver` | The specific topic subscription |
| 3 | Create/manage Search indexes and switch aliases | Ingestion | `Search Service Contributor` | Search service |
| 4 | Read and write Search documents | Ingestion | `Search Index Data Contributor` | Search service (or a single index, see below) |
| 5 | Query Search documents only | Query | `Search Index Data Reader` | Search service (or a single index) |
| 6 | Call the embeddings deployment | Ingestion | `Cognitive Services OpenAI User` | Azure OpenAI account |
| 7 | Call the chat deployment | Query | `Cognitive Services OpenAI User` | Azure OpenAI account |
| 8 | Read/write the Redis-backed workflow state store | Ingestion | Redis access policy `Data Owner` | Azure Cache for Redis instance |
| 9 | Read the Redis-backed active-version pointer | Query | Redis access policy `Data Reader` | Azure Cache for Redis instance |
| 10 | Read secrets from Key Vault (only if the optional secret store is deployed) | Ingestion and/or Query | `Key Vault Secrets User` | Key Vault |

Rows 8-9 are not Azure RBAC role assignments (`Microsoft.Authorization/roleAssignments`) -- Azure
Cache for Redis's Microsoft Entra ID integration uses its own **access-policy assignment**
concept layered over Redis's ACL system. They are listed here for completeness since they are the
functional equivalent for this pipeline's state store, and because they still follow the same
least-privilege pattern (`Data Owner` vs. `Data Reader`).

### Why the two OpenAI role assignments look identical

Row 6 and row 7 are the *same* role (`Cognitive Services OpenAI User`) on the *same* Azure OpenAI
account, once for each identity. Azure OpenAI's RBAC roles are account-scoped, not
deployment-scoped -- there is currently no built-in way to grant "inference on the embeddings
deployment only" separately from "inference on the chat deployment only" within one account. If
you need that level of isolation, deploy the embeddings and chat models to separate Azure OpenAI
accounts and assign each identity only to the account it needs.

### Per-index scoping (optional, tighter than the default)

Azure AI Search supports scoping `Search Index Data Contributor`/`Search Index Data Reader` to a
single index instead of the whole service:

```sh
az role assignment create \
  --assignee <principal-id> \
  --role "Search Index Data Reader" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<service>/indexes/<index-name>"
```

This sample does not do this by default because `DurableRAGPipeline` creates a *new* index per
version (`{index_base_name}-{version}`) -- a static per-index scope would need to be re-granted on
every version activation. `Search Service Contributor` (row 3) already limits the ingestion
identity's *index-management* surface to this one search service; per-index data-plane scoping is
a further tightening worth considering once you have a fixed, small set of versions in flight.

### Detailed citations

**Row 1 -- Storage Blob Data Reader.** Confirmed via [Azure built-in roles for
Storage](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/storage) and
corroborated by [Azure Storage's own blob-access-authorization
docs](https://learn.microsoft.com/azure/storage/blobs/authorize-data-operations-portal). Role ID
`2a2b9908-6ea1-4ae2-8e65-a410df84e7d1`. Description: "Allows for read access to Azure Storage blob
containers and data."

**Rows 2 -- Azure Service Bus Data Receiver.** Confirmed via [Azure built-in roles for
Integration](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/integration).
Role ID `4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0`. Description: "Allows for receive access to Azure
Service Bus resources." (The companion `Azure Service Bus Data Sender`, ID
`69a216fc-b8fb-44d8-bc22-1f3c2cd27a39`, is used in the Bicep for the Event Grid system topic's own
delivery identity -- not by either workload identity.)

**Rows 3-5 -- Search Service Contributor / Search Index Data Contributor / Search Index Data
Reader.** Confirmed via Azure AI Search's own RBAC doc, [Connect using Azure
roles](https://learn.microsoft.com/azure/search/search-security-rbac), which is more precise than
the general-purpose built-in-roles page for this product. That page's permissions table explicitly
lists **aliases** as one of the object types covered by `Search Service Contributor`'s "create,
run, and manage search objects" permission (footnote 1: "Includes indexes, indexers, data sources,
skillsets, aliases, synonym maps, debug sessions, knowledge bases, and knowledge sources") --
confirming that **switching the alias is a control-plane operation** requiring
`Search Service Contributor`, not a data-plane one. Role IDs: `Search Service Contributor`
`7ca78c08-252a-4471-8644-bb5ff32d4ba0`, `Search Index Data Contributor`
`8ebe5a00-799e-43f5-93ac-243d3dce84a7`, `Search Index Data Reader`
`1407120a-92aa-4202-b7e9-c0e197c71c8f`. `Search Index Data Contributor` is indeed a separate
data-plane role from `Search Service Contributor`, as the prompt for this doc anticipated needing
to check -- one manages index *definitions* (control plane), the other manages index *documents*
(data plane), and the ingestion identity needs both.

**Rows 6-7 -- Cognitive Services OpenAI User.** Confirmed via [Azure built-in roles for AI +
machine learning](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/ai-machine-learning)
for the exact role name, and via [Role-based access control for Azure
OpenAI](https://learn.microsoft.com/azure/ai-services/openai/how-to/role-based-access-control) for
its exact permitted/denied task list. Role ID `5e0bd9bd-7b93-4f28-af87-19fc36ad61ae`. Confirmed
capability relevant here: "Make inference API calls with Microsoft Entra ID" (covers both chat
completions and embeddings against already-deployed models). Confirmed it explicitly **cannot**:
create/edit model deployments, fine-tune models, view/copy/regenerate keys, or access quota -- so
neither identity can reconfigure the Azure OpenAI account, only call its already-deployed models.

**Rows 8-9 -- Redis access policies Data Owner / Data Reader.** Confirmed via [Use Microsoft Entra
for cache
authentication](https://learn.microsoft.com/azure/azure-cache-for-redis/cache-azure-active-directory-for-authentication)
(Azure Cache for Redis's own docs), which names the built-in access policies exactly as `Data
Owner`, `Data Contributor`, and `Data Reader`. That page also notes Microsoft Entra ID
authentication is **not supported on the Enterprise/Enterprise Flash tiers** of Azure Cache for
Redis (Basic/Standard/Premium only) -- relevant if you scale up to Enterprise for throughput or
clustering, since you would lose this managed-identity path and need to fall back to access keys
(see the commented-out alternative in
[`workflow-statestore.yaml`](../../examples/rag/components/azure/workflow-statestore.yaml)). That
same page also carries a retirement notice for Azure Cache for Redis across all SKUs in favor of
"Azure Managed Redis" -- see the flagged callout in
[`examples/rag/infra/README.md`](../../examples/rag/infra/README.md).

**Row 10 -- Key Vault Secrets User.** Confirmed via [Azure RBAC for Key
Vault](https://learn.microsoft.com/azure/key-vault/general/rbac-guide), which requires the vault to
use the "Azure role-based access control" permission model (this sample's Bicep sets
`enableRbacAuthorization: true`). Role ID `4633458b-17de-408a-b874-0445c86b69e6`. Description:
"Read secret contents including secret portion of a certificate with private key." This is
read-only for secret *values*; it cannot create, rotate, or delete secrets (that is `Key Vault
Secrets Officer`, a separate, more privileged role this pipeline's identities do not need).

## What this pipeline never needs

No identity in this design needs `Owner`, `Contributor`, or `User Access Administrator` at any
scope, a Storage/Search/OpenAI/Key Vault **management-plane write** role (e.g. `Search Service
Contributor`'s sibling for *creating the Search service itself* is a deployment-time concern
handled by whoever runs the Bicep, not a runtime identity), or any role at subscription or
resource-group scope. If a future change to this pipeline seems to need one of those, treat that as
a signal to re-scope the *specific* permission needed (via a resource-scoped built-in role, a
per-index/per-secret scope, or a custom role -- Azure AI Search's own docs show how to clone
`Search Index Data Reader` into a narrower custom role, for example) rather than reaching for a
broader built-in role.

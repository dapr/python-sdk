// Relays Blob Storage change events (BlobCreated / BlobDeleted) to the
// Service Bus topic via an Event Grid system topic + event subscription.
//
// UNVALIDATED, TRICKIEST PART OF THIS TEMPLATE -- see infra/README.md. If
// this module fails to deploy or behaves unexpectedly, the equivalent
// `az eventgrid` CLI steps documented there are the fallback: disable this
// module with `deployEventGridSubscription = false` and wire the
// subscription manually.
//
// Delivery uses the system topic's own system-assigned managed identity
// (deliveryWithResourceIdentity) rather than a connection string, so Event
// Grid itself needs "Azure Service Bus Data Sender" on the destination
// topic -- granted below, scoped to that one topic.

@description('Azure region. Kept the same as the storage account for simplicity.')
param location string

@description('Resource ID of the source storage account.')
param storageAccountId string

@description('Name of the source storage account (used to derive the system topic name).')
param storageAccountName string

@description('Name of the Service Bus namespace that owns the destination topic.')
param serviceBusNamespaceName string

@description('Name of the destination Service Bus topic.')
param serviceBusTopicName string

@description('Resource ID of the destination Service Bus topic.')
param serviceBusTopicId string

@description('Event subscription name.')
param eventSubscriptionName string = 'blob-to-servicebus'

@description('Tags applied to the system topic.')
param tags object = {}

var roleIdServiceBusDataSender = '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'

resource systemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: '${storageAccountName}-events'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: systemTopic
  name: eventSubscriptionName
  properties: {
    deliveryWithResourceIdentity: {
      identity: {
        type: 'SystemAssigned'
      }
      destination: {
        endpointType: 'ServiceBusTopic'
        properties: {
          resourceId: serviceBusTopicId
        }
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
    }
    eventDeliverySchema: 'EventGridSchema'
  }
}

resource existingSbNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' existing = {
  name: serviceBusNamespaceName
}

resource existingSbTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' existing = {
  parent: existingSbNamespace
  name: serviceBusTopicName
}

resource eventGridServiceBusSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(existingSbTopic.id, systemTopic.id, roleIdServiceBusDataSender)
  scope: existingSbTopic
  properties: {
    principalId: systemTopic.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIdServiceBusDataSender)
  }
}

output systemTopicName string = systemTopic.name
output eventSubscriptionName string = eventSubscription.name

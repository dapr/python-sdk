// Service Bus namespace + topic + subscription for the
// Event Grid -> Service Bus -> Dapr pub/sub trigger path. The topic receives
// Blob Storage change notifications (relayed by the Event Grid system topic
// in modules/eventgrid.bicep); the ingestion workload's Dapr sidecar
// consumes from `subscriptionName` via the servicebus-pubsub component
// (examples/rag/components/azure/servicebus-pubsub.yaml).

@description('Azure region.')
param location string

@description('Globally-unique Service Bus namespace name.')
param serviceBusNamespaceName string

@description('Namespace SKU. Standard or Premium -- Basic does not support topics.')
param skuName string = 'Standard'

@description('Topic name for Blob Storage change events.')
param topicName string

@description('Subscription name the ingestion workload consumes from.')
param subscriptionName string

@description('Tags applied to the namespace.')
param tags object = {}

resource sbNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' = {
  name: serviceBusNamespaceName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuName
  }
}

resource sbTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: sbNamespace
  name: topicName
  properties: {
    defaultMessageTimeToLive: 'P14D'
  }
}

resource sbSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: sbTopic
  name: subscriptionName
  properties: {
    maxDeliveryCount: 10
    lockDuration: 'PT5M'
    defaultMessageTimeToLive: 'P14D'
  }
}

output namespaceId string = sbNamespace.id
output namespaceName string = sbNamespace.name
output topicId string = sbTopic.id
output topicName string = sbTopic.name
output subscriptionName string = sbSubscription.name

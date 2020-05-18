#!/bin/bash
if [ -z $1 ]; then
  echo "Usage: ./log.sh <NAME>"
  echo "Example: ./log.sh demo-grpc-server"
  exit 1
fi


NAME=$1

echo "Fetching Logs..."

# Make sure container is Running
CONTAINER_STATE=$(kubectl get pods --selector=app=p-$NAME -o jsonpath='{.items[0].status.phase}')
while [ "$CONTAINER_STATE" != "Running" ]; do
  echo "Container state = $CONTAINER_STATE, awaiting 'Running'"
  CONTAINER_STATE=$(kubectl get pods --selector=app=p-$NAME -o jsonpath='{.items[0].status.phase}')
  sleep 1
done

# Log
echo "=================== DAPR Logs ===================="
kubectl logs --selector=app=p-$NAME -c daprd

echo "================= CONTAINER Logs ================="
kubectl logs -f --selector=app=p-$NAME -c c-$NAME

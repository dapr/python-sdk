#!/bin/bash

if [ -z $1 ]; then
  echo "Usage: ./start.sh <NAME>"
  echo "Example: ./start.sh demo-grpc-server"
  exit 1
fi

NAME=$1
DIRECTORY=`dirname $0`

echo "Deleting old deployment..."
kubectl delete deployment $NAME
echo "Creating deployment..."
kubectl apply -f ./Deploy/$NAME.yaml

sleep 3 # It's still processing the deployment recreate

echo "Opening logs"
$DIRECTORY/log.sh $NAME
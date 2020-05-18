#!/bin/bash

if [ -z $1 -o -z $2 ]; then
  echo "Usage: ./build.sh <NAME> <LOCATION_DOCKERFILE>"
  echo "Example: ./build.sh demo-grpc-server Server/"
  exit 1
fi

export DOCKER_IMAGE="$1:latest"
cd $2
docker build -t $DOCKER_IMAGE .
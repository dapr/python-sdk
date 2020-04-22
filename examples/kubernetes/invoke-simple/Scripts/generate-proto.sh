if [ -z $1 -o -z $2 ]; then
  echo "Usage: ./generate-proto.sh <LOCATION_PROTO> <OUTPUT_FOLDER>"
  echo "Example: ./generate-proto.sh Proto/ Server/Proto/"
  exit 1
fi

PROTO_FILE_LOCATION=$1
PROTO_OUTPUT_LOCATION=$2

mkdir -p $PROTO_OUTPUT_LOCATION

python3 -m grpc_tools.protoc --proto_path=$PROTO_FILE_LOCATION --python_out=$PROTO_OUTPUT_LOCATION --grpc_python_out=$PROTO_OUTPUT_LOCATION $PROTO_FILE_LOCATION/dapr.proto
python3 -m grpc_tools.protoc --proto_path=$PROTO_FILE_LOCATION --python_out=$PROTO_OUTPUT_LOCATION --grpc_python_out=$PROTO_OUTPUT_LOCATION $PROTO_FILE_LOCATION/daprclient.proto

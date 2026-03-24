# NOTE: These are only for durabletask!!

init:
	pip3 install -r requirements.txt

test-unit:
	pytest -m "not e2e" --verbose

test-e2e:
	pytest -m e2e --verbose

coverage-clean:
	rm -f .coverage .coverage.* coverage.xml

coverage-all: coverage-clean
	pytest -m "not e2e" --durations=0 --cov=durabletask --cov-branch --cov-report=term-missing --cov-report=xml
	pytest -m e2e --durations=0 --cov=durabletask --cov-branch --cov-report=term-missing --cov-report=xml --cov-append

install:
	python3 -m pip install .

gen-proto:
	curl -o durabletask/internal/orchestrator_service.proto https://raw.githubusercontent.com/dapr/durabletask-protobuf/refs/heads/main/protos/orchestrator_service.proto
	curl -H "Accept: application/vnd.github.v3+json" "https://api.github.com/repos/dapr/durabletask-protobuf/commits?path=protos/orchestrator_service.proto&sha=main&per_page=1" | jq -r '.[0].sha' > durabletask/internal/PROTO_SOURCE_COMMIT_HASH
	# NOTE: remember to check/update pyproject.toml protobuf version to follow https://github.com/grpc/grpc/blob/v{{VERSION GRPC IO TOOL BELLOW}}/tools/distrib/python/grpcio_tools/setup.py
	pip install .[dev]
	python3 -m grpc_tools.protoc --proto_path=.  --python_out=. --pyi_out=. --grpc_python_out=. ./durabletask/internal/orchestrator_service.proto
	rm durabletask/internal/*.proto

.PHONY: init test-unit test-e2e coverage-clean coverage-all gen-proto install

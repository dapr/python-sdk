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

DAPR_BRANCH ?= main
PROTO_URL = https://raw.githubusercontent.com/dapr/durabletask-protobuf/refs/heads/$(DAPR_BRANCH)/protos

gen-proto:
	curl -o durabletask/internal/orchestrator_service.proto $(PROTO_URL)/orchestrator_service.proto
	curl -o durabletask/internal/orchestration.proto $(PROTO_URL)/orchestration.proto
	curl -o durabletask/internal/history_events.proto $(PROTO_URL)/history_events.proto
	curl -o durabletask/internal/orchestrator_actions.proto $(PROTO_URL)/orchestrator_actions.proto
	curl -H "Accept: application/vnd.github.v3+json" "https://api.github.com/repos/dapr/durabletask-protobuf/commits?path=protos/orchestrator_service.proto&sha=$(DAPR_BRANCH)&per_page=1" | jq -r '.[0].sha' > durabletask/internal/PROTO_SOURCE_COMMIT_HASH
	# NOTE: remember to check/update pyproject.toml protobuf version to follow https://github.com/grpc/grpc/blob/v{{VERSION GRPC IO TOOL BELLOW}}/tools/distrib/python/grpcio_tools/setup.py
	pip install .[dev]
	# Rewrite bare inter-proto imports to full paths so protoc generates package-qualified Python imports
	perl -i -pe 's|import "([^/]+\.proto)"|import "durabletask/internal/$$1"|g' durabletask/internal/*.proto
	python3 -m grpc_tools.protoc \
		--proto_path=. \
		--python_out=. \
		--pyi_out=. \
		--grpc_python_out=. \
		durabletask/internal/orchestrator_service.proto \
		durabletask/internal/orchestration.proto \
		durabletask/internal/history_events.proto \
		durabletask/internal/orchestrator_actions.proto
	rm durabletask/internal/*.proto

.PHONY: init test-unit test-e2e coverage-clean coverage-all gen-proto install
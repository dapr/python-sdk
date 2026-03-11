# Example - Error handling

This guide demonstrates handling `DaprGrpcError` errors when using the Dapr python-SDK. It's important to note that not all Dapr gRPC status errors are currently captured and transformed into a `DaprGrpcError` by the SDK. Efforts are ongoing to enhance this aspect, and contributions are welcome. For detailed information on error handling in Dapr, refer to the [official documentation](https://docs.dapr.io/developing-applications/error-codes/).

The example involves creating a DaprClient and invoking the save_state method.
It uses the default configuration from Dapr init in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted).

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

To run this example, the following code can be used:

<!-- STEP
name: Run error handling example
expected_stdout_lines:
- "Status code: StatusCode.INVALID_ARGUMENT"
- "Message: input key/keyPrefix 'key||' can't contain '||'"
- "Error code: DAPR_STATE_ILLEGAL_KEY"
- "Error info(reason): DAPR_STATE_ILLEGAL_KEY"
- "Resource info (resource type): state"
- "Resource info (resource name): statestore"
- "Bad request (field): key||"
- "Bad request (description): input key/keyPrefix 'key||' can't contain '||'"
- "JSON: {\"status_code\": \"INVALID_ARGUMENT\", \"message\": \"input key/keyPrefix 'key||' can't contain '||'\", \"error_code\": \"DAPR_STATE_ILLEGAL_KEY\", \"details\": {\"error_info\": {\"@type\": \"type.googleapis.com/google.rpc.ErrorInfo\", \"reason\": \"DAPR_STATE_ILLEGAL_KEY\", \"domain\": \"dapr.io\"}, \"retry_info\": null, \"debug_info\": null, \"quota_failure\": null, \"precondition_failure\": null, \"bad_request\": {\"@type\": \"type.googleapis.com/google.rpc.BadRequest\", \"field_violations\": [{\"field\": \"key||\", \"description\": \"input key/keyPrefix 'key||' can't contain '||'\"}]}, \"request_info\": null, \"resource_info\": {\"@type\": \"type.googleapis.com/google.rpc.ResourceInfo\", \"resource_type\": \"state\", \"resource_name\": \"statestore\"}, \"help\": null, \"localized_message\": null}}"
timeout_seconds: 5
-->

```bash
dapr run --resources-path components  -- python3 error_handling.py
```
<!-- END_STEP -->

The output should be as follows:

```
Status code: INVALID_ARGUMENT
Message: input key/keyPrefix 'key||' can't contain '||'
Error code: DAPR_STATE_ILLEGAL_KEY
Error info(reason): DAPR_STATE_ILLEGAL_KEY
Resource info (resource type): state
Resource info (resource name): statestore
Bad request (field): key||
Bad request (description): input key/keyPrefix 'key||' can't contain '||'
JSON: {"status_code": "INVALID_ARGUMENT", "message": "input key/keyPrefix 'key||' can't contain '||'", "error_code": "DAPR_STATE_ILLEGAL_KEY", "details": {"error_info": {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "DAPR_STATE_ILLEGAL_KEY", "domain": "dapr.io"}, "retry_info": null, "debug_info": null, "quota_failure": null, "precondition_failure": null, "bad_request": {"@type": "type.googleapis.com/google.rpc.BadRequest", "field_violations": [{"field": "key||", "description": "input key/keyPrefix 'key||' can't contain '||'"}]}, "request_info": null, "resource_info": {"@type": "type.googleapis.com/google.rpc.ResourceInfo", "resource_type": "state", "resource_name": "statestore"}, "help": null, "localized_message": null}}
```

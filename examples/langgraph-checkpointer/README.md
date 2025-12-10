# Dapr For Agents - LangGraph Checkpointer

Supporting Dapr backed Checkpointer for LangGraph based Agents.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install -r requirements.txt
```

## Run the example

Export your `OPENAI_API_KEY`:

```bash
export OPENAI_API_KEY="SK-..."
```

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
  - '== APP == Add 3 and 4.'
  - '== APP == Tool Calls:'
  - '== APP ==   add'
  - '== APP ==  Call'
  - '== APP ==     a: 3'
  - '== APP ==     b: 4'
  - '== APP == Name: add'
  - '== APP == 7'
  - '== APP == The result of adding 3 and 4 is 7.'
  - '== APP == Multiply that by 2.'
  - '== APP ==   Args:'
  - '== APP ==     a: 7'
  - '== APP ==     b: 2'
  - '== APP == ================================= Tool Message ================================='
  - '== APP == Name: multiply'
  - '== APP == '
  - '== APP == 14'
  - '== APP == ================================== Ai Message =================================='
  - '== APP == '
  - '== APP == The result of multiplying 7 by 2 is 14.'
    
output_match_mode: substring
background: true
match_order: none
sleep: 15
-->

```bash
# 1. Run the LangGraph agent
dapr run --app-id langgraph-checkpointer --app-port 5001 --resources-path ./components -- python3 agent.py
```

<!-- END_STEP -->

## Cleanup

Either press CTRL + C to quit the app or run the following command in a new terminal to stop the app:

```bash
dapr stop --app-id langgraph-checkpointer
```


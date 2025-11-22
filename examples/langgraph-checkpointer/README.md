# Dapr For Agents - LangGraph Checkpointer

Supporting Dapr backed Checkpointer for LangGraph based Agents.

1. Initialize Dapr

```shell
dapr init
```

2. Install dependencies either with
```shell
uv sync
```
or 
```shell
pip install -r requirements.txt
```

3. Ensure to correct the template file for `.env` with your OpenAI API Key

4. Run the agent
```shell
dapr run -f dapr.yaml
```

This will provision the redis state store (which we use in this example, see `./components/memory.yaml`) to store the state, the Checkpointer, for the LangGraph agent to have short term memory. See [State Management](https://docs.dapr.io/developing-applications/building-blocks/state-management/) for more details on State Managenent and [LangGraph - Memory](https://docs.langchain.com/oss/python/langgraph/add-memory) for details on LangGraph Agent Memory.

This example is based on the LangGraph Academy Demo repository for [agent-memory in module-1](https://github.com/langchain-ai/langchain-academy/blob/b20cf608f2bf165e09080961537d329f813cfb20/module-1/agent-memory.ipynb).
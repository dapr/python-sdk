from dapr.ext.langgraph import DaprCheckpointer
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


def add(a: int, b: int) -> int:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b


tools = [add, multiply]
llm = ChatOllama(model='llama3.2:latest')
llm_with_tools = llm.bind_tools(tools)

sys_msg = SystemMessage(
    content='You are a helpful assistant tasked with performing arithmetic on a set of inputs.'
)


def assistant(state: MessagesState):
    return {'messages': [llm_with_tools.invoke([sys_msg] + state['messages'])]}


builder = StateGraph(MessagesState)

builder.add_node('assistant', assistant)
builder.add_node('tools', ToolNode(tools))

builder.add_edge(START, 'assistant')
builder.add_conditional_edges(
    'assistant',
    tools_condition,
)
builder.add_edge('tools', 'assistant')

memory = DaprCheckpointer(store_name='statestore', key_prefix='dapr')
react_graph_memory = builder.compile(checkpointer=memory)
memory.set_agent(react_graph_memory)

config = {'configurable': {'thread_id': '1'}}

messages = [HumanMessage(content='Add 3 and 4.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

messages = [HumanMessage(content='Multiply the result by 2.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

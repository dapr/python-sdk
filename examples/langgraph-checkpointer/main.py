import os

from dapr.ext.langgraph import DaprCheckpointer
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()


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
llm = ChatOpenAI(model='gpt-4o', api_key=os.environ['OPENAI_API_KEY'])
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

memory = DaprCheckpointer(store_name='dapr-redis', key_prefix='dapr')
react_graph_memory = builder.compile(checkpointer=memory)

config = {'configurable': {'thread_id': '1'}}

messages = [HumanMessage(content='Add 3 and 4.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

messages = [HumanMessage(content='Multiply that by 2.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

memory = DaprCheckpointer(store_name='dapr-sqlite', key_prefix='dapr')
react_graph_memory = builder.compile(checkpointer=memory)

config = {'configurable': {'thread_id': '2'}}

messages = [HumanMessage(content='Add 5 and 6.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

messages = [HumanMessage(content='Multiply that by 3.')]
messages = react_graph_memory.invoke({'messages': messages}, config)
for m in messages['messages']:
    m.pretty_print()

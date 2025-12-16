import asyncio
from typing import List, Tuple, Union
import json
from autogen_core import AgentId
from autogen_core.models import UserMessage
from autogen_core.tools import FunctionTool
import inspect
from opentelemetry import trace
from pydantic import BaseModel, Field
from tools.tool_tracing_utils import trace_span_info

from utils.logger import get_logger

logger = get_logger()


class DelegationTask(BaseModel):
    agent: str = Field(..., description="The agent to delegate the task to.")
    task: str = Field(..., description="The details of the task to be delegated.")
    name: str = Field(..., description="The name of the agent delegating the task.")


@trace_span_info
async def delegate_tasks(
    delegation_tasks: Union[List[DelegationTask], str],
) -> List[Tuple[str, List[UserMessage]]]:
    """
    Groups delegation tasks by agent and prepares a single combined message per agent.

    Args:
        delegation_tasks (Union[List[DelegationTask], str]): A list of tasks or a string
        representation of it.

    Returns:
        List[Tuple[str, List[UserMessage]]]: A list of tuples with the agent and their
        combined tasks.
    """
    if isinstance(delegation_tasks, str):
        delegation_tasks = [DelegationTask(**t) for t in eval(delegation_tasks)]

    parsed_delegation_tasks = [
        (task.agent, [UserMessage(content=task.task, source=task.name)])
        for task in delegation_tasks
    ]

    return parsed_delegation_tasks


async def set_communication_tools(agent_topics, communication_tools, runtime):
    assert communication_tools, "No communication tools found"

    # get descriptions of agents available
    agents_descriptions = await asyncio.gather(
        *[get_agent_description(topic_id, runtime) for topic_id in agent_topics]
    )

    for tool in communication_tools:
        tool.description = tool.description.format(
            agents="- " + "\n\n- ".join(agents_descriptions)
        )

    return dict([(tool.name, tool) for tool in communication_tools])


async def get_agent_description(topic_id, runtime):
    metadata = await runtime.agent_metadata(AgentId(topic_id, "default"))
    agent_description = metadata["description"]
    logger.info("Agent description for %s: %s", topic_id, agent_description)
    return f"{topic_id}: {agent_description}"

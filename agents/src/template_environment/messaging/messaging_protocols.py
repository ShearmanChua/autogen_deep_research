from typing import List

from autogen_core.models import LLMMessage
from pydantic import BaseModel


class UserTask(BaseModel):
    """
    A message sent from the user to the agent system.

    sender_topic_type: The topic type of the agent that should receive this message.
    context: A list of LLMMessage objects that contain the conversation history leading
    up to this message.
    """

    sender_topic_type: str
    context: List[LLMMessage]


class AgentTask(BaseModel):
    """
    A message sent from one agent to another agent.

    sender_topic_type: The topic type of the agent that should receive this message.
    context: A list of LLMMessage objects that contain the conversation history leading
    up to this message.
    """

    sender_topic_type: str
    context: List[LLMMessage]


class BroadCastMessage(BaseModel):
    """
    A message sent from one agent to all agents.

    sender_topic_type: The topic type of the agent that should receive this message.
    context: A list of LLMMessage objects that contain the conversation history leading
    up to this message.
    """

    sender_topic_type: str
    context: List[LLMMessage]


class AgentResponse(BaseModel):
    """
    A response from an agent to a UserTask message.

    sender_topic_type: The topic type of the UserTask message that this response is
    replying to.
    context: A list of LLMMessage objects that contain the conversation history leading
    up to this message.
    """

    sender_topic_type: str
    context: List[LLMMessage]

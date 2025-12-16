import asyncio
import uuid

import utils.tracer as tracer

from agents.base_thinking_agent import BaseThinkingAgent
from agents.user_agent import UserAgent
from autogen_core import SingleThreadedAgentRuntime, TopicId
from autogen_core.models import UserMessage
from configs import agents_config, runtime_config
from messaging.messaging import setup_messaging_topics
from messaging.messaging_protocols import UserTask
from utils.logger import get_logger, setup_logger

# TODO: Replace all PLACEHOLDER with concrete names

setup_logger()
logger = get_logger()

session_id = str(uuid.uuid4())


async def main():
    # instantiate trace provider
    logger.info("Instantiating trace provider")
    _ = tracer.set_phoenix_tracer_provider(
        project_name="PLACEHOLDER_project_name",
        session_id=session_id,
    )
    # instantiate runtime
    logger.info("Instantiating runtime")
    runtime = SingleThreadedAgentRuntime()
    # Instantiate all agents
    logger.info("Instantiating all agents")
    agents = {}
    for user in agents_config.user_cfgs:
        agents[user["name"]] = await UserAgent.register(
            runtime,
            type=user["name"],
            factory=lambda user_cfgs=user: UserAgent(
                description=user_cfgs["description"],
                user_topic=user_cfgs["user_topic_type"],
                agent_topic=user_cfgs["agent_topic_type"],
            ),
        )
    for agent in agents_config.autonomous_agents_cfgs:
        agent_name = agent["name"]
        del agent["name"]
        agents[agent_name] = await BaseThinkingAgent.register(
            runtime,
            type=agent_name,
            factory=lambda agent_cfgs=agent: BaseThinkingAgent(**agent_cfgs),
        )

    logger.info("Instantiating message queue")
    await setup_messaging_topics(runtime, agents, "PLACEHOLDER_BROADCAST")
    # Start running task
    logger.info("Starting runtime")
    runtime.start()
    await runtime.publish_message(
        UserTask(
            sender_topic_type="User",
            context=[UserMessage(content=runtime_config.prompt, source="User")],
            broadcast=False,
        ),
        topic_id=TopicId("User", "PLACEHOLDER_ID"),
    )
    logger.info("Message published")
    await runtime.stop_when_idle()  # Stop processing messages in the background.


if __name__ == "__main__":
    asyncio.run(main())

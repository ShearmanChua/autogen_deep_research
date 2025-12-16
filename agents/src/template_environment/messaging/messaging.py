from typing import Dict

from autogen_core import AgentId, SingleThreadedAgentRuntime, TypeSubscription


async def setup_messaging_topics(
    runtime: SingleThreadedAgentRuntime,
    agents: Dict[str, AgentId],
    broadcast_topic_type: str = "PLACEHOLDER_BROADCAST",
) -> None:
    """
    Sets up messaging topics for a list of agents within the provided runtime.

    This function subscribes each agent to its own topic and a common broadcast topic,
    allowing them to receive messages directed specifically to them as well as general
    broadcast messages.

    Args:
        runtime (SingleThreadedAgentRuntime): The runtime environment managing the
        agents.
        agents (List[RoutedAgent]): A list of agents to set up messaging topics for.
        broadcast_topic_type (str, optional): The topic type for broadcast messages.
            Defaults to "PLACEHOLDER_BROADCAST".

    Returns:
        None
    """

    for _, agent_id in agents.items():
        await runtime.add_subscription(
            TypeSubscription(topic_type=agent_id.type, agent_type=agent_id.type)
        )

    for _, agent_id in agents.items():
        # for all agents except users, subscribe to the broadcast topic
        if agent_id.type != "User":
            await runtime.add_subscription(
                TypeSubscription(
                    topic_type=broadcast_topic_type, agent_type=agent_id.type
                )
            )

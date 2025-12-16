from autogen_core import MessageContext, RoutedAgent, TopicId, message_handler
from autogen_core.models import (
    LLMMessage,
)
from opentelemetry import trace
from typing import List

from messaging.messaging_protocols import AgentResponse, UserTask
from utils.logger import get_logger

logger = get_logger()


class UserAgent(RoutedAgent):
    def __init__(self, description: str, user_topic: str, agent_topic: str) -> None:
        super().__init__(description)
        self._user_topic = user_topic
        self._agent_topic = agent_topic
        self._chat_history: List[LLMMessage] = []

    @message_handler
    async def handle_user_message(self, message: UserTask, ctx: MessageContext) -> None:
        """
        Handle a UserTask message by broadcasting it to an agent.

        Args:
            message: The UserTask message to be handled.
            ctx: The message context.
        """
        logger.info("Received message:\n%s", message.context)
        logger.info("Sending message to %s agent", self._agent_topic)

        # add message to chat history
        self._chat_history.extend(message.context)

        # send message to triage agent
        await self.publish_message(
            message,
            topic_id=TopicId(self._agent_topic, source=self.id.key),
        )

    @message_handler
    async def handle_task_result(
        self, message: AgentResponse, ctx: MessageContext
    ) -> None:
        """
        Handle a response from a triage agent.

        This message handler is called when the user agent receives a response from
        the triage agent that was delegated a task and returned the result.

        Args:
            message: The message containing the response from the triage agent.
            ctx: The message context.

        Returns:
            None
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("AgentResponse") as span:
            span.set_attribute("openinference.span.kind", "LLM")
            for idx, hist_message in enumerate(self._chat_history):
                role = "user" if hist_message.source == "User" else "assistant"
                span.set_attribute(
                    f"llm.input_messages.{idx}.message.content", hist_message.content
                )
                span.set_attribute(
                    f"llm.input_messages.{idx}.message.name", hist_message.source
                )
                span.set_attribute(f"llm.input_messages.{idx}.message.role", role)

            span.set_attribute(
                "llm.output_messages.0.message.content", message.context[0].content
            )
            span.set_attribute("llm.output_messages.0.message.role", "assistant")
            span.set_attribute(
                "llm.output_messages.0.message.name", message.context[0].source
            )

        self._chat_history.extend(message.context)
        assistant_msg = message.context[0]
        logger.info(
            "Final response for %s:\n%s",
            self.id.key,
            assistant_msg.content,
        )
        return

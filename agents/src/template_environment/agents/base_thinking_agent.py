import json
import copy
from typing import List

from autogen_core import (
    AgentId,
    FunctionCall,
    MessageContext,
    RoutedAgent,
    TopicId,
    message_handler,
)
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    CreateResult,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    UserMessage,
    LLMMessage,
    SystemMessage,
)
from autogen_core.tools import Tool
from messaging.messaging_protocols import AgentTask, UserTask, BroadCastMessage, AgentResponse
from reflection.base_reflection import BaseReflection
from tools.communication_tools import set_communication_tools
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from utils.logger import get_logger

from opentelemetry.trace import get_current_span

logger = get_logger()


class BaseThinkingAgent(RoutedAgent):
    def __init__(
        self,
        description: str,
        system_message: str,
        model_client: ChatCompletionClient,
        agent_topics: List[str] = [],
        broadcast_topic: str = None,
        tools: List[Tool] = [],
        communication_tools: List[Tool] = [],
    ):

        super().__init__(description)
        self._system_message = SystemMessage(content=system_message)
        self._model_client = model_client
        self._tools = dict([(tool.name, tool) for tool in tools])
        self._runtime_execution_graph = (
            self._runtime.execution_graph
            if hasattr(self._runtime, "execution_graph")
            else None
        )
        self._communication_tools = communication_tools
        self._agent_topics = agent_topics
        self._broadcast_topic = broadcast_topic
        self._chat_history: List[LLMMessage] = []
        self._sender_agent_topic = ""
        self._reflection = BaseReflection(system_message=system_message)
        self._num_tool_calls = 0

    @message_handler
    async def handle_broadcast_message(
        self, message: BroadCastMessage, ctx: MessageContext
    ) -> None:
        if ctx.sender != self.id:
            self._system_message.content += (
                f"\n\nCurrent task context: {message.context[0].content}"
            )

    @message_handler
    async def handle_user_task(self, message: UserTask, ctx: MessageContext) -> None:
        """
        Handle a UserTask message and broadcasts it to all agents if
        broadcast_topic_type is not None.

        Then, sends the chat history to the LLM to generate a response, or
        a list of function calls, or delegate them. If a response message is returned,
        send the LLM response back to the user.

        Args:
            message: The UserTask message to be handled.
            ctx: The message context.
        """

        # designate message soure topic type
        self._sender_agent_topic = message.sender_topic_type

        if not isinstance(self._communication_tools, dict) and self._communication_tools:
            self._communication_tools = await set_communication_tools(
                self._agent_topics, self._communication_tools, self._runtime
            )

        if self._broadcast_topic:

            broadcast_message = BroadCastMessage(
                sender_topic_type=self.id.type, context=message.context
            )
            # broadcast the message to all agents
            logger.info("Broadcasting message")
            await self.publish_message(
                broadcast_message,
                topic_id=TopicId(self._broadcast_topic, source=self.id.key),
            )

        self._chat_history.extend(message.context)
        
        think_context = await self._reflection.think(copy.deepcopy(self._chat_history),
                                                     self._model_client,
                                                     self.id.type)
        
        self._chat_history.extend(think_context)

        available_tools = (
            [tool.schema for tool in self._tools.values()]
            + [tool.schema for tool in self._communication_tools]
            if self._communication_tools
            else [tool.schema for tool in self._tools.values()]
        )
        current_span = get_current_span()
        current_span.set_attribute("available tools", str(available_tools))

        # Run user task
        llm_result = await self._model_client.create(
            messages=[self._system_message] + self._chat_history,
            tools=available_tools,
            cancellation_token=ctx.cancellation_token,
        )

        logger.info("LLM result: %s", llm_result)

        # if the LLM returns a list of function calls
        # handle function calls
        if isinstance(llm_result.content, list) and all(
            isinstance(m, FunctionCall) for m in llm_result.content
        ):
            await self.handle_function_calls(llm_result, ctx)
        else:
            await self.handle_response(llm_result, ctx)

    @message_handler
    async def handle_agent_task(self, message: AgentTask, ctx: MessageContext) -> None:
        """
        Handles AgentTask message.

        This message handler is called when the agent receives a task from another
        agent. It adds the task to the chat history and sends the chat
        history to the LLM. If the LLM returns a list of function calls,
        the agent runs them. Otherwise, the agent sends the LLM response
        back to the sending agent.

        Args:
            message: The AgentTask message to be handled.
            ctx: The message context.

        Returns:
            None
        """
        # add message to chat history
        if self._chat_history and self._chat_history[-1].type == "UserMessage":
            self._chat_history[-1].content += f"\n\n{message.context[-1].content}"
        else:
            self._chat_history.extend(message.context)
        # update topic type of agent to reply to
        self._sender_agent_topic = message.sender_topic_type

        if not isinstance(self._communication_tools, dict) and self._communication_tools:
            self._communication_tools = await set_communication_tools(
                self._agent_topics, self._communication_tools, self._runtime
            )

        available_tools = (
            [tool.schema for tool in self._tools.values()]
            + [tool.schema for tool in self._communication_tools]
            if self._communication_tools
            else [tool.schema for tool in self._tools.values()]
        )
        current_span = get_current_span()
        current_span.set_attribute("available tools", str(available_tools))

        # analyse agent task
        llm_result = await self._model_client.create(
            messages=[self._system_message] + self._chat_history,
            tools=available_tools,
            cancellation_token=ctx.cancellation_token,
        )

        if isinstance(llm_result.content, list) and all(
            isinstance(m, FunctionCall) for m in llm_result.content
        ):
            self._tool_result = []
            self._delegate_tool_result = []
            await self.handle_function_calls(llm_result, ctx)

    async def handle_function_calls(
        self, llm_result: CreateResult, ctx: MessageContext
    ) -> None:
        """
        Process a list of function calls returned by the LLM and execute them using
        the appropriate tools or delegate tools.

        This method appends the function calls to the chat history, executes each
        function call using the corresponding tool or delegate tool, and appends
        the execution results to the chat history. If there are delegate targets,
        it further delegates tasks to the specified agents.

        Args:
            llm_result: The result of the LLM, which contains a list of function
                        calls to be processed.
            ctx: The message context which includes a cancellation token for
                managing task cancellation.

        Returns:
            None
        """

        # add message to chat history
        self._chat_history.append(
            AssistantMessage(content=llm_result.content, source=self.id.type)
        )
        
        tool_results = []
        # Process each function call.
        for call in llm_result.content:
            self._num_tool_calls += 1
            arguments = json.loads(call.arguments)

            if call.name in self._tools:
                logger.info("Running tool: %s", call.name)

                try:
                    tool_result = await self._tools[call.name].run_json(
                        arguments, ctx.cancellation_token
                    )
                    # save tool results
                    tool_results.append(
                        FunctionExecutionResult(
                            name=call.name,
                            content=self._tools[call.name].return_value_as_string(
                                tool_result
                            ),
                            call_id=call.id,
                        )
                    )
                except Exception as e:
                    tool_results.append(
                        FunctionExecutionResult(
                            name=call.name,
                            content=str(e),
                            call_id=call.id,
                            is_error=True,
                        )
                    )
            elif call.name in self._communication_tools:
                try:
                    tool_result = await self._communication_tools[call.name].run_json(
                        arguments, ctx.cancellation_token
                    )
                    # save tool results
                    tool_results.append(
                        FunctionExecutionResult(
                            name=call.name,
                            content=self._communication_tools[call.name].return_value_as_string(
                                tool_result
                            ),
                            call_id=call.id,
                        )
                    )
                except Exception as e:
                    tool_results.append(
                        FunctionExecutionResult(
                            name=call.name,
                            content=str(e),
                            call_id=call.id,
                            is_error=True,
                        )
                    )
            # if no such tool exists
            else:

                try:
                    tracer = trace.get_tracer(__name__)
                    with tracer.start_as_current_span(call.name) as span:
                        arguments = json.loads(call.arguments)
                        span.set_attribute("status", "ERROR")
                        span.set_status(Status(StatusCode.ERROR))
                        span.set_attribute("openinference.span.kind", "TOOL")
                        span.set_attribute("tool.name", call.name)
                        span.set_attribute("tool.description", "Invalid tool")
                        span.set_attribute("input.value", call.arguments)
                        span.set_attribute(
                            "output.value",
                            f"Exception: {call.name} is not a valid tool",
                        )
                        span.set_attribute("tool.parameters", list(arguments.keys()))
                        raise Exception(f"{call.name} is not a valid tool")
                except Exception:
                    pass

                tool_results.append(
                    FunctionExecutionResult(
                        name=call.name,
                        content=f"NameError: {call.name} is not a valid tool",
                        call_id=call.id,
                        is_error=True,
                    )
                )

        # add tool results to chat history
        self._chat_history.append(
            FunctionExecutionResultMessage(content=tool_results)
        )

        if self._num_tool_calls > 3:
            think_context = await self._reflection.think(copy.deepcopy(self._chat_history),
                                                        self._model_client,
                                                        self.id.type)
            
            self._chat_history.extend(think_context)
            self._num_tool_calls = 0

        available_tools = (
            [tool.schema for tool in self._tools.values()]
            + [tool.schema for tool in self._communication_tools]
            if self._communication_tools
            else [tool.schema for tool in self._tools.values()]
        )

        # analyse agent task
        llm_result = await self._model_client.create(
            messages=[self._system_message] + self._chat_history,
            tools=available_tools,
            cancellation_token=ctx.cancellation_token,
        )

        if isinstance(llm_result.content, list) and all(
            isinstance(m, FunctionCall) for m in llm_result.content
        ):
            await self.handle_function_calls(llm_result, ctx)

        # if LLM response is not a list of function calls, and no agent delegation
        # is required send it back to sender
        else:
            await self.handle_response(llm_result, ctx)

    async def handle_response(
        self, llm_result: CreateResult, ctx: MessageContext
    ) -> None:
        self._chat_history.append(AssistantMessage(content=llm_result.content, source=self.id.type))
        await self.publish_message(
            AgentResponse(
                sender_topic_type=self.id.type,
                context=[
                    AssistantMessage(
                        content=llm_result.content, source=self.id.type
                    )
                ],
            ),
            topic_id=TopicId(self._sender_agent_topic, source=self.id.key),
        )
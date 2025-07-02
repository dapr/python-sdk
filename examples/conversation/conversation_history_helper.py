#!/usr/bin/env python3

"""
Simple Conversation History Helper

A lightweight helper for managing conversation history in multi-turn conversations.
Handles conversation accumulation, tool calling context, basic history management,
and usage tracking without complex summarization logic.

For more advanced use cases (like intelligent summarization), users can implement
their own custom history management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dapr.clients.grpc._request import ContentPart, ConversationInput, TextContent, ToolCallContent
from dapr.clients.grpc._response import (
    ConversationResponse,
    ConversationStreamComplete,
    ConversationUsage,
)


@dataclass
class UsageInfo:
    """Represents usage information for a conversation turn."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0  # Total cost (can be calculated or provided directly)
    input_cost: float = 0.0  # Cost for input/prompt tokens
    output_cost: float = 0.0  # Cost for output/completion tokens
    model: Optional[str] = None
    provider: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dapr_usage(cls, dapr_usage: ConversationUsage, model: Optional[str] = None, provider: Optional[str] = None, cost: float = 0.0, input_cost: float = 0.0, output_cost: float = 0.0) -> 'UsageInfo':
        """Create UsageInfo from Dapr ConversationUsage object."""
        return cls(
            prompt_tokens=dapr_usage.prompt_tokens,
            completion_tokens=dapr_usage.completion_tokens,
            total_tokens=dapr_usage.total_tokens,
            cost=cost,
            input_cost=input_cost,
            output_cost=output_cost,
            model=model,
            provider=provider
        )

    @classmethod
    def from_response(cls, response: Union[ConversationResponse, ConversationStreamComplete], model: Optional[str] = None, provider: Optional[str] = None, cost: float = 0.0, input_cost: float = 0.0, output_cost: float = 0.0) -> Optional['UsageInfo']:
        """Create UsageInfo from Dapr response object if usage is available."""
        if hasattr(response, 'usage') and response.usage:
            return cls.from_dapr_usage(response.usage, model, provider, cost, input_cost, output_cost)
        return None

    @classmethod
    def calculate_cost(
        cls,
        dapr_usage: ConversationUsage,
        cost_per_million_input_tokens: float,
        cost_per_million_output_tokens: float,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> 'UsageInfo':
        """
        Create UsageInfo with calculated costs based on token usage and pricing.

        Args:
            dapr_usage: Usage information from Dapr response
            cost_per_million_input_tokens: Cost per million input/prompt tokens
            cost_per_million_output_tokens: Cost per million output/completion tokens
            model: Model name
            provider: Provider name

        Returns:
            UsageInfo with calculated costs
        """
        input_cost = (dapr_usage.prompt_tokens / 1_000_000) * cost_per_million_input_tokens
        output_cost = (dapr_usage.completion_tokens / 1_000_000) * cost_per_million_output_tokens
        total_cost = input_cost + output_cost

        return cls(
            prompt_tokens=dapr_usage.prompt_tokens,
            completion_tokens=dapr_usage.completion_tokens,
            total_tokens=dapr_usage.total_tokens,
            cost=total_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            model=model,
            provider=provider
        )

    @classmethod
    def from_response_with_pricing(
        cls,
        response: Union[ConversationResponse, ConversationStreamComplete],
        cost_per_million_input_tokens: float,
        cost_per_million_output_tokens: float,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Optional['UsageInfo']:
        """
        Create UsageInfo from Dapr response with automatic cost calculation.

        Args:
            response: Dapr response object
            cost_per_million_input_tokens: Cost per million input/prompt tokens
            cost_per_million_output_tokens: Cost per million output/completion tokens
            model: Model name
            provider: Provider name

        Returns:
            UsageInfo with calculated costs, or None if no usage info available
        """
        if hasattr(response, 'usage') and response.usage:
            return cls.calculate_cost(
                response.usage,
                cost_per_million_input_tokens,
                cost_per_million_output_tokens,
                model,
                provider
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'cost': self.cost,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'model': self.model,
            'provider': self.provider,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ConversationTurn:
    """Represents a complete conversation turn (user + assistant + tools)."""
    user_message: str
    assistant_message: Optional[str] = None
    tools: Optional[List[Any]] = None
    tool_calls: Optional[List[Any]] = None
    tool_results: Optional[List[Any]] = None
    usage: Optional[UsageInfo] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'user_message': self.user_message,
            'assistant_message': self.assistant_message,
            'tools': [str(tool) for tool in (self.tools or [])],
            'tool_calls': [str(call) for call in (self.tool_calls or [])],
            'tool_results': [str(result) for result in (self.tool_results or [])],
            'usage': self.usage.to_dict() if self.usage else None,
            'timestamp': self.timestamp.isoformat()
        }


class ConversationHistoryManager:
    """
    Simple conversation history manager for multi-turn conversations.

    Features:
    - Automatic conversation accumulation for multi-turn contexts
    - Tool calling context preservation
    - Simple history trimming based on complete conversation turns
    - Built-in usage tracking and cost monitoring
    - Provider-specific optimizations
    """

    def __init__(
        self,
        max_turns: int = 10,
        provider_name: str = "openai",
        track_usage: bool = True
    ):
        """
        Initialize conversation history manager.

        Args:
            max_turns: Maximum number of complete conversation turns to keep
            provider_name: Name of the LLM provider for optimization
            track_usage: Whether to track usage information
        """
        self.max_turns = max_turns
        self.provider_name = provider_name.lower()
        self.track_usage = track_usage

        # Conversation state
        self.turns: List[ConversationTurn] = []
        self.current_turn: Optional[ConversationTurn] = None

        # Usage tracking
        self.total_usage = UsageInfo() if track_usage else None

    def add_user_message(
        self,
        content: str,
        tools: Optional[List[Any]] = None,
        usage: Optional[Union[UsageInfo, ConversationUsage, ConversationResponse, ConversationStreamComplete]] = None
    ) -> None:
        """
        Add a user message to start a new conversation turn.

        Args:
            content: The user's message content
            tools: Optional list of tools available for this turn
            usage: Optional usage information (can be UsageInfo, ConversationUsage, or response objects)
        """
        # Finalize previous turn if exists
        if self.current_turn and self.current_turn.assistant_message:
            self.turns.append(self.current_turn)
            self._trim_history()

        # Extract usage if provided
        extracted_usage = self._extract_usage(usage)

        # Start new turn
        self.current_turn = ConversationTurn(
            user_message=content,
            tools=tools,
            usage=extracted_usage
        )

        # Update total usage
        if extracted_usage and self.track_usage:
            self._add_to_total_usage(extracted_usage)

    def add_assistant_message(self, response: ConversationResponse) -> None:
        """
        Adds an assistant's response to the current conversation turn using a
        ConversationResponse object as the single source of truth.

        Args:
            response: The ConversationResponse object from the Dapr client or
                      a manually constructed one for testing.
        """
        if not self.current_turn:
            raise ValueError("No active conversation turn. Call add_user_message first.")

        # Extract content and tool calls from the response
        all_text = [out.get_text() for out in response.outputs if out.get_text()]
        content = "\n".join(all_text) if all_text else None

        all_tool_calls = []
        for out in response.outputs:
            all_tool_calls.extend(out.get_tool_calls())
        tool_calls = all_tool_calls or None

        # Extract usage from the provided source
        extracted_usage = self._extract_usage(response)

        self.current_turn.assistant_message = content
        self.current_turn.tool_calls = tool_calls

        # Merge usage information
        if extracted_usage and self.track_usage:
            if self.current_turn.usage:
                # Combine with existing usage
                self.current_turn.usage.prompt_tokens += extracted_usage.prompt_tokens
                self.current_turn.usage.completion_tokens += extracted_usage.completion_tokens
                self.current_turn.usage.total_tokens += extracted_usage.total_tokens
                self.current_turn.usage.cost += extracted_usage.cost
                self.current_turn.usage.input_cost += extracted_usage.input_cost
                self.current_turn.usage.output_cost += extracted_usage.output_cost
            else:
                self.current_turn.usage = extracted_usage

            self._add_to_total_usage(extracted_usage)

    def add_tool_results(
        self,
        results: List[Any],
        usage: Optional[Union[UsageInfo, ConversationUsage, ConversationResponse, ConversationStreamComplete]] = None
    ) -> None:
        """
        Add tool execution results to the current conversation turn.

        Args:
            results: List of tool execution results
            usage: Optional usage information for tool processing
        """
        if not self.current_turn:
            raise ValueError("No active conversation turn. Call add_user_message first.")

        # Extract usage if provided
        extracted_usage = self._extract_usage(usage)

        self.current_turn.tool_results = results

        # Update usage if provided
        if extracted_usage and self.track_usage:
            if self.current_turn.usage:
                self.current_turn.usage.prompt_tokens += extracted_usage.prompt_tokens
                self.current_turn.usage.completion_tokens += extracted_usage.completion_tokens
                self.current_turn.usage.total_tokens += extracted_usage.total_tokens
                self.current_turn.usage.cost += extracted_usage.cost
                self.current_turn.usage.input_cost += extracted_usage.input_cost
                self.current_turn.usage.output_cost += extracted_usage.output_cost
            else:
                self.current_turn.usage = extracted_usage

            self._add_to_total_usage(extracted_usage)

    def _extract_usage(self, usage: Optional[Union[UsageInfo, ConversationUsage, ConversationResponse, ConversationStreamComplete]]) -> Optional[UsageInfo]:
        """Extract UsageInfo from various input types."""
        if not usage or not self.track_usage:
            return None

        if isinstance(usage, UsageInfo):
            return usage
        elif isinstance(usage, ConversationUsage):
            return UsageInfo.from_dapr_usage(usage, provider=self.provider_name)
        elif isinstance(usage, (ConversationResponse, ConversationStreamComplete)):
            return UsageInfo.from_response(usage, provider=self.provider_name)
        else:
            # Try to extract usage from response-like object
            if hasattr(usage, 'usage') and usage.usage:
                return UsageInfo.from_dapr_usage(usage.usage, provider=self.provider_name)

        return None

    def _add_to_total_usage(self, usage: UsageInfo) -> None:
        """Add usage to running totals."""
        if not self.total_usage:
            return

        self.total_usage.prompt_tokens += usage.prompt_tokens
        self.total_usage.completion_tokens += usage.completion_tokens
        self.total_usage.total_tokens += usage.total_tokens
        self.total_usage.cost += usage.cost
        self.total_usage.input_cost += usage.input_cost
        self.total_usage.output_cost += usage.output_cost

    def get_conversation_inputs(self) -> List[ConversationInput]:
        """
        Get conversation inputs for the Dapr API.

        For multi-turn conversations, this returns accumulated conversation history.
        For single-turn conversations, returns just the current input.

        Returns:
            List of ConversationInput objects ready for Dapr API
        """
        inputs = []

        # Add completed turns
        for turn in self.turns:
            # Add user message
            user_parts = [ContentPart(text=TextContent(text=turn.user_message))]
            # NOTE: Tools are now passed at request level, not as content parts

            inputs.append(ConversationInput(
                role="user",
                parts=user_parts
            ))

            # Add assistant message if available
            if turn.assistant_message:
                assistant_parts = [ContentPart(text=TextContent(text=turn.assistant_message))]

                # Add tool calls if any
                if turn.tool_calls:
                    for tool_call in turn.tool_calls:
                        # Create ToolCallContent using flat structure
                        tool_call_content = ToolCallContent(
                            id=tool_call.id,
                            type='function',
                            name=tool_call.name,
                            arguments=tool_call.arguments
                        )
                        assistant_parts.append(ContentPart(tool_call=tool_call_content))

                inputs.append(ConversationInput(
                    role="assistant",
                    parts=assistant_parts
                ))

                # Add tool results if any
                if turn.tool_results:
                    for result in turn.tool_results:
                        tool_result = ToolResultContent(
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                            content=result
                        )
                        inputs.append(ConversationInput(
                            role="tool",
                            parts=[ContentPart(tool_result=tool_result)]
                        ))

        # Add current turn if it exists
        if self.current_turn:
            user_parts = [ContentPart(text=TextContent(text=self.current_turn.user_message))]
            # NOTE: Tools are now passed at request level, not as content parts

            inputs.append(ConversationInput(
                role="user",
                parts=user_parts
            ))

        return inputs

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive usage summary.

        Returns:
            Dictionary containing usage statistics and breakdown
        """
        if not self.track_usage or not self.total_usage:
            return {'usage_tracking_enabled': False}

        # Calculate per-turn breakdown
        turn_breakdown = []
        for i, turn in enumerate(self.turns):
            if turn.usage:
                turn_breakdown.append({
                    'turn': i + 1,
                    'tokens': turn.usage.total_tokens,
                    'prompt_tokens': turn.usage.prompt_tokens,
                    'completion_tokens': turn.usage.completion_tokens,
                    'cost': turn.usage.cost,
                    'input_cost': turn.usage.input_cost,
                    'output_cost': turn.usage.output_cost,
                    'tool_calls': len(turn.tool_calls) if turn.tool_calls else 0,
                    'timestamp': turn.usage.timestamp.isoformat()
                })

        # Add current turn if it has usage
        if self.current_turn and self.current_turn.usage:
            turn_breakdown.append({
                'turn': len(self.turns) + 1,
                'tokens': self.current_turn.usage.total_tokens,
                'prompt_tokens': self.current_turn.usage.prompt_tokens,
                'completion_tokens': self.current_turn.usage.completion_tokens,
                'cost': self.current_turn.usage.cost,
                'input_cost': self.current_turn.usage.input_cost,
                'output_cost': self.current_turn.usage.output_cost,
                'tool_calls': len(self.current_turn.tool_calls) if self.current_turn.tool_calls else 0,
                'timestamp': self.current_turn.usage.timestamp.isoformat()
            })

        # Calculate statistics
        total_turns = len(self.turns) + (1 if self.current_turn else 0)
        avg_cost_per_turn = self.total_usage.cost / total_turns if total_turns > 0 else 0
        avg_tokens_per_turn = self.total_usage.total_tokens / total_turns if total_turns > 0 else 0

        return {
            'usage_tracking_enabled': True,
            'summary': {
                'total_cost': self.total_usage.cost,
                'input_cost': self.total_usage.input_cost,
                'output_cost': self.total_usage.output_cost,
                'total_tokens': self.total_usage.total_tokens,
                'prompt_tokens': self.total_usage.prompt_tokens,
                'completion_tokens': self.total_usage.completion_tokens,
                'avg_cost_per_turn': avg_cost_per_turn,
                'avg_tokens_per_turn': avg_tokens_per_turn
            },
            'breakdown': turn_breakdown,
            'conversation_stats': {
                'total_turns': total_turns,
                'complete_turns': len(self.turns),
                'total_messages': len(self.get_conversation_inputs()),
                'tool_calls': sum(len(turn.tool_calls) if turn.tool_calls else 0 for turn in self.turns),
                'provider': self.provider_name
            }
        }

    def _trim_history(self) -> None:
        """Trim conversation history to stay within max_turns limit."""
        if len(self.turns) > self.max_turns:
            # Remove oldest turns while preserving usage information
            self.turns = self.turns[-self.max_turns:]

            # Usage information is preserved in total_usage, so no action needed

    def reset(self) -> None:
        """Reset conversation history and usage tracking."""
        self.turns.clear()
        self.current_turn = None
        if self.track_usage:
            self.total_usage = UsageInfo()


# Provider-specific factory functions
def create_history_manager(provider_name: str, **kwargs) -> ConversationHistoryManager:
    """
    Create a conversation history manager optimized for a specific provider.

    Args:
        provider_name: Name of the LLM provider ("openai", "anthropic", "google", etc.)
        **kwargs: Additional arguments passed to ConversationHistoryManager

    Returns:
        ConversationHistoryManager instance with provider-specific defaults
    """
    provider_defaults = {
        "openai": {"max_turns": 20},
        "anthropic": {"max_turns": 15},
        "google": {"max_turns": 18},
        "mistral": {"max_turns": 16},
        "deepseek": {"max_turns": 16},
    }

    # Apply provider-specific defaults
    defaults = provider_defaults.get(provider_name.lower(), {"max_turns": 15})

    # User-provided kwargs override defaults
    config = {**defaults, **kwargs}
    config["provider_name"] = provider_name

    return ConversationHistoryManager(**config)


if __name__ == "__main__":
    # Simple test
    manager = create_history_manager("openai")

    # Simulate a conversation with usage tracking
    manager.add_user_message("Hello!", usage=UsageInfo(prompt_tokens=5, total_tokens=5))
    # Note: We create a dummy ConversationResponse for the test
    from dapr.clients.grpc._response import (
        ContentPart,
        ConversationOutput,
        ConversationResponse,
        TextContent,
    )
    dummy_response = ConversationResponse(
        outputs=[ConversationOutput(parts=[ContentPart(text=TextContent(text="Hi there!"))])],
        usage=UsageInfo(completion_tokens=10, total_tokens=10)
    )
    manager.add_assistant_message(dummy_response)

    print("Usage Summary:")
    summary = manager.get_usage_summary()
    print(f"Total tokens: {summary['summary']['total_tokens']}")
    print(f"Total cost: ${summary['summary']['total_cost']:.6f}")
    print(f"Turns: {summary['conversation_stats']['total_turns']}")

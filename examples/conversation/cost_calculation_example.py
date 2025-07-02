#!/usr/bin/env python3

"""
Cost Calculation Example

Demonstrates how to use the conversation history helper with proper cost calculation
based on separate input and output token pricing for different LLM providers.

This example shows:
1. Provider-specific pricing configurations
2. Automatic cost calculation from API responses
3. Manual cost calculation with custom pricing
4. Detailed cost breakdown and analysis
"""

from typing import Dict

from examples.conversation.conversation_history_helper import UsageInfo, create_history_manager

# Provider pricing configurations (cost per million tokens)
PROVIDER_PRICING = {
    "openai": {
        "gpt-4o": {
            "input": 2.50,   # $2.50 per million input tokens
            "output": 10.00  # $10.00 per million output tokens
        },
        "gpt-4o-mini": {
            "input": 0.15,   # $0.15 per million input tokens
            "output": 0.60   # $0.60 per million output tokens
        },
        "gpt-3.5-turbo": {
            "input": 0.50,   # $0.50 per million input tokens
            "output": 1.50   # $1.50 per million output tokens
        }
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,   # $3.00 per million input tokens
            "output": 15.00  # $15.00 per million output tokens
        },
        "claude-3-5-haiku-20241022": {
            "input": 0.80,   # $0.80 per million input tokens
            "output": 4.00   # $4.00 per million output tokens
        }
    },
    "google": {
        "gemini-2.0-flash-exp": {
            "input": 0.075,  # $0.075 per million input tokens
            "output": 0.30   # $0.30 per million output tokens
        },
        "gemini-1.5-pro": {
            "input": 1.25,   # $1.25 per million input tokens
            "output": 5.00   # $5.00 per million output tokens
        }
    }
}


def get_pricing(provider: str, model: str) -> Dict[str, float]:
    """Get pricing for a specific provider and model."""
    provider_config = PROVIDER_PRICING.get(provider.lower(), {})
    model_config = provider_config.get(model, {})

    if not model_config:
        print(f"Warning: No pricing found for {provider}/{model}, using default rates")
        return {"input": 1.0, "output": 3.0}  # Default fallback pricing

    return model_config


def simulate_dapr_usage(prompt_tokens: int, completion_tokens: int):
    """Simulate a Dapr ConversationUsage object."""
    class MockUsage:
        def __init__(self, prompt_tokens: int, completion_tokens: int):
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens
            self.total_tokens = prompt_tokens + completion_tokens

    return MockUsage(prompt_tokens, completion_tokens)


def demonstrate_cost_calculation():
    """Demonstrate different ways to calculate and track costs."""

    print("🧮 LLM Cost Calculation Examples")
    print("=" * 50)

    # Example 1: Manual cost calculation
    print("\n1️⃣  Manual Cost Calculation")
    print("-" * 30)

    # Simulate usage data
    usage = simulate_dapr_usage(prompt_tokens=1500, completion_tokens=800)
    pricing = get_pricing("openai", "gpt-4o")

    # Calculate costs manually
    cost_info = UsageInfo.calculate_cost(
        usage,
        cost_per_million_input_tokens=pricing["input"],
        cost_per_million_output_tokens=pricing["output"],
        model="gpt-4o",
        provider="openai"
    )

    print(f"Model: {cost_info.model}")
    print(f"Provider: {cost_info.provider}")
    print(f"Input tokens: {cost_info.prompt_tokens:,}")
    print(f"Output tokens: {cost_info.completion_tokens:,}")
    print(f"Total tokens: {cost_info.total_tokens:,}")
    print(f"Input cost: ${cost_info.input_cost:.6f}")
    print(f"Output cost: ${cost_info.output_cost:.6f}")
    print(f"Total cost: ${cost_info.cost:.6f}")

    # Example 2: Using conversation history manager
    print("\n2️⃣  Conversation History with Cost Tracking")
    print("-" * 45)

    manager = create_history_manager("openai", max_turns=5)

    # Turn 1: Simple question
    usage1 = simulate_dapr_usage(prompt_tokens=1200, completion_tokens=600)
    pricing1 = get_pricing("openai", "gpt-4o-mini")
    cost1 = UsageInfo.calculate_cost(
        usage1, pricing1["input"], pricing1["output"],
        model="gpt-4o-mini", provider="openai"
    )

    manager.add_user_message("What is machine learning?", usage=cost1)
    manager.add_assistant_message(
        "Machine learning is a subset of artificial intelligence...",
        usage=cost1
    )

    # Turn 2: Follow-up with tool calling
    usage2 = simulate_dapr_usage(prompt_tokens=1800, completion_tokens=400)
    cost2 = UsageInfo.calculate_cost(
        usage2, pricing1["input"], pricing1["output"],
        model="gpt-4o-mini", provider="openai"
    )

    manager.add_user_message("Can you give me examples?", usage=cost2)
    manager.add_assistant_message(
        "I'll search for some examples for you.",
        tool_calls=[{"id": "call_1", "name": "search_examples", "arguments": "{}"}],
        usage=cost2
    )

    # Turn 3: More expensive model for complex reasoning
    usage3 = simulate_dapr_usage(prompt_tokens=2500, completion_tokens=1200)
    pricing3 = get_pricing("openai", "gpt-4o")
    cost3 = UsageInfo.calculate_cost(
        usage3, pricing3["input"], pricing3["output"],
        model="gpt-4o", provider="openai"
    )

    manager.add_user_message("Explain deep learning architectures in detail", usage=cost3)
    manager.add_assistant_message(
        "Deep learning architectures involve multiple layers of neural networks...",
        usage=cost3
    )

    # Get detailed usage summary
    summary = manager.get_usage_summary()

    print(f"Total conversation cost: ${summary['summary']['total_cost']:.6f}")
    print(f"Input costs: ${summary['summary']['input_cost']:.6f}")
    print(f"Output costs: ${summary['summary']['output_cost']:.6f}")
    print(f"Total tokens: {summary['summary']['total_tokens']:,}")
    print(f"Average cost per turn: ${summary['summary']['avg_cost_per_turn']:.6f}")

    print("\n📊 Per-Turn Breakdown:")
    for turn in summary['breakdown']:
        print(f"  Turn {turn['turn']}: ${turn['cost']:.6f} "
              f"(${turn['input_cost']:.6f} input + ${turn['output_cost']:.6f} output) "
              f"- {turn['tokens']:,} tokens")

    # Example 3: Compare costs across providers
    print("\n3️⃣  Provider Cost Comparison")
    print("-" * 35)

    # Same usage across different providers
    test_usage = simulate_dapr_usage(prompt_tokens=2000, completion_tokens=1000)

    providers_to_test = [
        ("openai", "gpt-4o"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("anthropic", "claude-3-5-haiku-20241022"),
        ("google", "gemini-2.0-flash-exp"),
        ("google", "gemini-1.5-pro")
    ]

    print(f"For {test_usage.prompt_tokens:,} input + {test_usage.completion_tokens:,} output tokens:")
    print()

    costs = []
    for provider, model in providers_to_test:
        pricing = get_pricing(provider, model)
        cost_info = UsageInfo.calculate_cost(
            test_usage, pricing["input"], pricing["output"],
            model=model, provider=provider
        )
        costs.append((provider, model, cost_info))

        print(f"{provider:10} {model:25} ${cost_info.cost:.6f} "
              f"(${cost_info.input_cost:.6f} + ${cost_info.output_cost:.6f})")

    # Find cheapest and most expensive
    costs.sort(key=lambda x: x[2].cost)
    cheapest = costs[0]
    most_expensive = costs[-1]

    print(f"\n💰 Cheapest: {cheapest[0]} {cheapest[1]} - ${cheapest[2].cost:.6f}")
    print(f"💸 Most expensive: {most_expensive[0]} {most_expensive[1]} - ${most_expensive[2].cost:.6f}")
    print(f"📈 Cost difference: {most_expensive[2].cost / cheapest[2].cost:.1f}x")


def demonstrate_real_api_integration():
    """Show how to integrate with real API responses."""

    print("\n4️⃣  Real API Integration Example")
    print("-" * 40)

    # Simulate a real API response structure
    class MockResponse:
        def __init__(self, prompt_tokens: int, completion_tokens: int):
            self.usage = simulate_dapr_usage(prompt_tokens, completion_tokens)

    # Example: Processing a real API response
    response = MockResponse(prompt_tokens=1500, completion_tokens=800)

    # Method 1: Automatic cost calculation from response
    pricing = get_pricing("anthropic", "claude-3-5-sonnet-20241022")
    cost_info = UsageInfo.from_response_with_pricing(
        response,
        cost_per_million_input_tokens=pricing["input"],
        cost_per_million_output_tokens=pricing["output"],
        model="claude-3-5-sonnet-20241022",
        provider="anthropic"
    )

    if cost_info:
        print("✅ Automatic cost calculation from API response:")
        print(f"   Cost: ${cost_info.cost:.6f} (${cost_info.input_cost:.6f} + ${cost_info.output_cost:.6f})")
        print(f"   Tokens: {cost_info.total_tokens:,} ({cost_info.prompt_tokens:,} + {cost_info.completion_tokens:,})")

    # Method 2: Using with conversation manager
    manager = create_history_manager("anthropic")

    # Add message with automatic cost calculation
    manager.add_user_message("Analyze this data", usage=cost_info)
    manager.add_assistant_message("Here's my analysis...", usage=cost_info)

    summary = manager.get_usage_summary()
    print("\n📊 Conversation summary:")
    print(f"   Total cost: ${summary['summary']['total_cost']:.6f}")
    print(f"   Input/Output split: ${summary['summary']['input_cost']:.6f} / ${summary['summary']['output_cost']:.6f}")


if __name__ == "__main__":
    demonstrate_cost_calculation()
    demonstrate_real_api_integration()

    print("\n" + "=" * 50)
    print("✨ Cost calculation examples completed!")
    print("\nKey features:")
    print("• Separate input/output token pricing")
    print("• Automatic cost calculation from API responses")
    print("• Provider-specific pricing configurations")
    print("• Detailed cost breakdowns and analysis")
    print("• Easy integration with conversation history")

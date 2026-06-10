# Approximate costs per 1000 tokens as of 2026
MODEL_COSTS = {
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-8": {"input": 0.015, "output": 0.075},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

# Session total tracker
_session_cost = 0.0


def track_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Track cost of an LLM API call.
    
    Args:
        model: Model name string
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
    
    Returns:
        cost: Cost of this specific call in USD
    """
    global _session_cost

    if model not in MODEL_COSTS:
        return 0.0

    cost = (
        (input_tokens / 1000) * MODEL_COSTS[model]["input"] +
        (output_tokens / 1000) * MODEL_COSTS[model]["output"]
    )

    _session_cost += cost
    print(f"Cost: ${cost:.4f} | Session total: ${_session_cost:.4f}")
    return cost


def get_session_cost() -> float:
    """Return total cost for this session."""
    return _session_cost


def reset_session_cost():
    """Reset session cost tracker."""
    global _session_cost
    _session_cost = 0.0
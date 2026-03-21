from app.security.identity import verify_identity
from app.security.policy import evaluate_tool_call


def test_policy_allows_research_tool():
    identity = verify_identity("analyst-1", "research")
    decision = evaluate_tool_call(identity, "firecrawl.agent.search", "research", {"firecrawl.agent.search"})
    assert decision.allowed is True
    assert decision.requires_interrupt is False


def test_policy_interrupts_sensitive_intent():
    identity = verify_identity("analyst-1", "database_write")
    decision = evaluate_tool_call(identity, "firecrawl.agent.search", "database_write", {"firecrawl.agent.search"})
    assert decision.allowed is False
    assert decision.requires_interrupt is True

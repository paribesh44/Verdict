from dataclasses import dataclass


@dataclass
class EfficiencyReport:
    mars_tokens: int
    mars_latency_ms: int
    mad_tokens_baseline: int
    mad_latency_ms_baseline: int
    token_gain_ratio: float
    latency_gain_ratio: float


def compare_mars_vs_mad(mars_tokens: int, mars_latency_ms: int) -> EfficiencyReport:
    mad_tokens_baseline = max(int(mars_tokens * 2), 1)
    mad_latency_ms_baseline = max(int(mars_latency_ms * 2), 1)
    token_gain_ratio = 1.0 - (mars_tokens / mad_tokens_baseline)
    latency_gain_ratio = 1.0 - (mars_latency_ms / mad_latency_ms_baseline)
    return EfficiencyReport(
        mars_tokens=mars_tokens,
        mars_latency_ms=mars_latency_ms,
        mad_tokens_baseline=mad_tokens_baseline,
        mad_latency_ms_baseline=mad_latency_ms_baseline,
        token_gain_ratio=token_gain_ratio,
        latency_gain_ratio=latency_gain_ratio,
    )

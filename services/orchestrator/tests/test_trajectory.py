from app.telemetry.trajectory import TrajectoryLogger


def test_trajectory_logger_records_steps():
    logger = TrajectoryLogger()
    logger.record("trace-x", "author", precision=0.9, recall=0.8, token_estimate=100, latency_ms=50)
    data = logger.as_dicts()
    assert len(data) == 1
    assert data[0]["trace_id"] == "trace-x"
    assert data[0]["step_name"] == "author"

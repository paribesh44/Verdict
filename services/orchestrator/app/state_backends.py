"""Factory for approval store, trajectory logger, and extraction store backends (Redis vs in-memory)."""

from __future__ import annotations

import os

from app.approvals import ApprovalStore, RedisApprovalStore
from app.extraction_store import ExtractionStore, RedisExtractionStore
from app.telemetry.trajectory import RedisTrajectoryLogger, TrajectoryLogger


def get_approval_store() -> ApprovalStore:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisApprovalStore(redis_url)
    return ApprovalStore()


def get_trajectory_logger() -> TrajectoryLogger:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisTrajectoryLogger(redis_url)
    return TrajectoryLogger()


def get_extraction_store() -> ExtractionStore:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisExtractionStore(redis_url)
    return ExtractionStore()

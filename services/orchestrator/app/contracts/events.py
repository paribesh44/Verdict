from datetime import datetime
from typing import Any, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class EventBase(BaseModel):
    event_id: str = Field(alias="eventId")
    trace_id: str = Field(alias="traceId")
    timestamp: datetime

    model_config = ConfigDict(populate_by_name=True)


class TextMessagePayload(BaseModel):
    role: Literal["system", "assistant", "user", "tool"]
    content: str


class ToolCallStartPayload(BaseModel):
    tool_name: str = Field(alias="toolName")
    call_id: str = Field(alias="callId")
    arguments: Dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class StateDeltaPayload(BaseModel):
    path: str
    op: Literal["replace", "append", "merge"]
    value: Any


class InterruptPayload(BaseModel):
    approval_id: str = Field(alias="approvalId")
    reason: str
    requested_action: str = Field(alias="requestedAction")

    model_config = ConfigDict(populate_by_name=True)


class TextMessageEvent(EventBase):
    event_type: Literal["TEXT_MESSAGE_CONTENT"] = Field(alias="eventType")
    payload: TextMessagePayload


class ToolCallStartEvent(EventBase):
    event_type: Literal["TOOL_CALL_START"] = Field(alias="eventType")
    payload: ToolCallStartPayload


class StateDeltaEvent(EventBase):
    event_type: Literal["STATE_DELTA"] = Field(alias="eventType")
    payload: StateDeltaPayload


class InterruptEvent(EventBase):
    event_type: Literal["INTERRUPT"] = Field(alias="eventType")
    payload: InterruptPayload


AGUIEvent = Union[TextMessageEvent, ToolCallStartEvent, StateDeltaEvent, InterruptEvent]

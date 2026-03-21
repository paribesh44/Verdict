from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Binding(BaseModel):
    prop: str
    path: str


class SurfaceComponent(BaseModel):
    id: str
    component: str
    props: Optional[Dict[str, Any]] = None
    bindings: Optional[List[Binding]] = None


class DataUpdate(BaseModel):
    path: str
    op: Literal["replace", "append", "merge"]
    value: Any


class EnvelopeBase(BaseModel):
    request_id: str = Field(alias="requestId")
    timestamp: datetime

    model_config = ConfigDict(populate_by_name=True)


class SurfaceUpdateEnvelope(EnvelopeBase):
    type: Literal["surfaceUpdate"]
    components: List[SurfaceComponent]


class DataModelUpdateEnvelope(EnvelopeBase):
    type: Literal["dataModelUpdate"]
    updates: List[DataUpdate]


class BeginRenderingEnvelope(EnvelopeBase):
    type: Literal["beginRendering"]
    surface_id: str = Field(alias="surfaceId")


A2UIEnvelope = Union[SurfaceUpdateEnvelope, DataModelUpdateEnvelope, BeginRenderingEnvelope]

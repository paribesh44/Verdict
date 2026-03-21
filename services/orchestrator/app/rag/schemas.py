from typing import List

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    source_url: str = Field(alias="sourceUrl")
    quote: str

    model_config = ConfigDict(populate_by_name=True)


class ClaimExtraction(BaseModel):
    claim_id: str = Field(alias="claimId")
    text: str
    confidence: float
    citations: List[Citation]

    model_config = ConfigDict(populate_by_name=True)


class ExtractionBundle(BaseModel):
    query: str
    claims: List[ClaimExtraction]

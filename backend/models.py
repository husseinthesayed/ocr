from pydantic import BaseModel
from typing import Dict, List, Any, Optional


class Field(BaseModel):
    field: str
    raw_value: str
    display_value: str
    confidence: int
    memory_corrected: bool = False


class ExtractResponse(BaseModel):
    fields: List[Dict[str, Any]]
    filename: str
    engine_used: str


class CorrectRequest(BaseModel):
    corrections: Dict[str, str]


class CorrectResponse(BaseModel):
    status: str
    new_entries: int
    total_entries: int


class MemoryResponse(BaseModel):
    corrections: Dict[str, str]
    count: int

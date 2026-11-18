from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LookupIn(BaseModel):
    location: str = Field(min_length=2, max_length=200)
    start_date: date
    end_date: date
    units: str = "celsius"
    notes: str = ""
    tags: str = ""
    pick_first: bool = False

    @field_validator("units")
    @classmethod
    def units_ok(cls, v):
        v = (v or "celsius").lower()
        if v not in {"celsius", "fahrenheit"}:
            raise ValueError("units must be celsius or fahrenheit")
        return v

    @field_validator("location")
    @classmethod
    def loc_ok(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("location is empty")
        return v


class LookupPatch(BaseModel):
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    units: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None
    pick_first: bool = False

    @field_validator("units")
    @classmethod
    def units_ok(cls, v):
        if v is None:
            return v
        v = v.lower()
        if v not in {"celsius", "fahrenheit"}:
            raise ValueError("units must be celsius or fahrenheit")
        return v

"""Pydantic schemas: define the shape of API requests and responses."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BusinessCreate(BaseModel):
    name: str
    category: str  # "general_purpose" | "industrial" | "hotel"


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    created_at: datetime


class BillCreate(BaseModel):
    business_id: int
    bill_date: date
    kwh: float
    submitted_amount: float | None = None  # what the user's real bill said, if they have one


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    bill_date: date
    kwh: float
    submitted_amount: float | None
    calculated_amount: float | None
    mismatch: float | None
    tariff_effective_from: str | None
    created_at: datetime
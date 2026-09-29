"""The actual database tables."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.models.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)   # "general_purpose" | "industrial" | "hotel"
    created_at = Column(DateTime, server_default=func.now())

    bills = relationship("Bill", back_populates="business")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)

    bill_date = Column(Date, nullable=False)          # which month this bill covers
    kwh = Column(Float, nullable=False)                # consumption for the month

    submitted_amount = Column(Float, nullable=True)    # what the user's actual bill said (LKR)
    calculated_amount = Column(Float, nullable=True)   # what our tariff engine computed
    mismatch = Column(Float, nullable=True)             # calculated_amount - submitted_amount

    tariff_effective_from = Column(String, nullable=True)  # which tariff file version was used

    created_at = Column(DateTime, server_default=func.now())

    business = relationship("Business", back_populates="bills")
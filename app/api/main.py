"""FastAPI application: endpoints for businesses and bills."""
from datetime import date
from app.recommendations.rules import generate_suggestions
from app.tariff_engine.carbon import calculate_carbon_kg
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import BusinessCreate, BusinessOut, BillCreate, BillOut
from app.models.database import get_db
from app.models.models import Business, Bill
from app.tariff_engine.calculator import calculate_bill
from app.tariff_engine.loader import load_tariff_for_date

app = FastAPI(title="SME Energy Advisor")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/businesses", response_model=BusinessOut)
def create_business(payload: BusinessCreate, db: Session = Depends(get_db)):
    business = Business(name=payload.name, category=payload.category)
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@app.get("/businesses", response_model=list[BusinessOut])
def list_businesses(db: Session = Depends(get_db)):
    return db.query(Business).all()


def _compute_bill(business: Business, bill_date: date, kwh: float) -> dict:
    """Shared logic: run the tariff engine for one business/date/kwh combination."""
    tariff = load_tariff_for_date(bill_date)
    result = calculate_bill(business.category, kwh, tariff)
    return {
        "calculated_amount": result.total,
        "tariff_effective_from": tariff["effective_from"],
    }


@app.post("/bills", response_model=BillOut)
def create_bill(payload: BillCreate, db: Session = Depends(get_db)):
    business = db.get(Business, payload.business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    computed = _compute_bill(business, payload.bill_date, payload.kwh)

    mismatch = None
    if payload.submitted_amount is not None:
        mismatch = computed["calculated_amount"] - payload.submitted_amount

    bill = Bill(
        business_id=payload.business_id,
        bill_date=payload.bill_date,
        kwh=payload.kwh,
        submitted_amount=payload.submitted_amount,
        calculated_amount=computed["calculated_amount"],
        mismatch=mismatch,
        tariff_effective_from=computed["tariff_effective_from"],
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@app.get("/bills", response_model=list[BillOut])
def list_bills(business_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Bill)
    if business_id is not None:
        query = query.filter(Bill.business_id == business_id)
    return query.order_by(Bill.bill_date).all()


@app.post("/bills/{bill_id}/recalculate", response_model=BillOut)
def recalculate_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    business = db.get(Business, bill.business_id)
    computed = _compute_bill(business, bill.bill_date, bill.kwh)

    bill.calculated_amount = computed["calculated_amount"]
    bill.tariff_effective_from = computed["tariff_effective_from"]
    if bill.submitted_amount is not None:
        bill.mismatch = bill.calculated_amount - bill.submitted_amount

    db.commit()
    db.refresh(bill)
    return bill

@app.get("/bills/{bill_id}/carbon")
def get_bill_carbon(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    return {
        "bill_id": bill.id,
        "kwh": bill.kwh,
        "carbon_kg": calculate_carbon_kg(bill.kwh),
    }

@app.get("/bills/{bill_id}/savings")
def get_bill_savings(bill_id: int, db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    business = db.get(Business, bill.business_id)
    tariff = load_tariff_for_date(bill.bill_date)

    recent_bills = (
        db.query(Bill)
        .filter(Bill.business_id == bill.business_id, Bill.bill_date <= bill.bill_date)
        .order_by(Bill.bill_date)
        .all()
    )
    recent_kwh = [b.kwh for b in recent_bills]

    suggestions = generate_suggestions(
        kwh=bill.kwh,
        category=business.category,
        tariff=tariff,
        recent_kwh=recent_kwh,
        mismatch=bill.mismatch,
        calculated_amount=bill.calculated_amount or 0,
    )

    return {
        "bill_id": bill.id,
        "suggestions": [
            {"title": s.title, "detail": s.detail, "priority": s.priority}
            for s in suggestions
        ],
    }
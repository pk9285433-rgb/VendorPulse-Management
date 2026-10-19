from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import Base, engine, get_db
from .models import Vendor, PurchaseOrder, PurchaseOrderItem
from .analytics import vendor_performance
from app import analytics

Base.metadata.create_all(bind=engine)
app = FastAPI(title="VendorPulse Management API", version="1.0.0",
              description="Vendor performance and explainable rule-based risk analytics.")

@app.get("/health")
def health():
    return {"status": "ok", "service": "VendorPulse Management API"}

@app.get("/api/vendors")
def list_vendors(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                 search: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Vendor)
    if search:
        pattern = f"%{search}%"
        q = q.filter((Vendor.vendor_id.ilike(pattern)) | (Vendor.city.ilike(pattern)) | (Vendor.state.ilike(pattern)))
    total = q.count()
    items = q.order_by(Vendor.vendor_id).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset,
            "items": [{"vendor_id": v.vendor_id, "city": v.city, "state": v.state,
                       "zip_code_prefix": v.zip_code_prefix} for v in items]}

@app.get("/api/vendors/{vendor_id}")
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    v = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
    if not v:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")
    performance = next((x for x in vendor_performance(db) if x["vendor_id"] == vendor_id), None)
    return {"vendor": {"vendor_id": v.vendor_id, "city": v.city, "state": v.state,
                       "zip_code_prefix": v.zip_code_prefix}, "performance": performance}

@app.get("/api/analytics/summary")
def summary(db: Session = Depends(get_db)):
    rows = vendor_performance(db)
    known = [x["on_time_delivery_pct"] for x in rows if x["on_time_delivery_pct"] is not None]
    risks = [x["risk_score"] for x in rows if x["risk_score"] is not None]
    return {
        "vendor_count": db.query(func.count(Vendor.vendor_id)).scalar() or 0,
        "order_count": db.query(func.count(PurchaseOrder.order_id)).scalar() or 0,
        "order_item_count": db.query(func.count(PurchaseOrderItem.id)).scalar() or 0,
        "vendors_with_delivery_metrics": len(known),
        "average_on_time_delivery_pct": round(sum(known)/len(known), 2) if known else None,
        "average_vendor_risk_score": round(sum(risks)/len(risks), 2) if risks else None
    }

@app.get("/api/analytics/vendor-performance")
def performance(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
                min_orders: int = Query(1, ge=0), db: Session = Depends(get_db)):
    rows = [x for x in vendor_performance(db) if x["order_count"] >= min_orders]
    rows.sort(key=lambda x: (x["on_time_delivery_pct"] is None, -(x["on_time_delivery_pct"] or 0)))
    return {"total": len(rows), "limit": limit, "offset": offset, "items": rows[offset:offset+limit]}

@app.get("/api/analytics/vendor-risks")
def risks(risk_tier: str | None = Query(None, pattern="^(High|Medium|Low|Insufficient Data)$"),
          limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
          db: Session = Depends(get_db)):
    rows = vendor_performance(db)
    if risk_tier:
        rows = [x for x in rows if x["risk_tier"] == risk_tier]
    rows.sort(key=lambda x: (x["risk_score"] is None, -(x["risk_score"] or 0)))
    return {"total": len(rows), "limit": limit, "offset": offset, "items": rows[offset:offset+limit]}
@app.get("/api/analytics/vendor-scorecard")
def get_vendor_scorecard(
    vendor_id: str,
    db: Session = Depends(get_db),
):
    result = analytics.vendor_scorecard(db, vendor_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    return result


@app.get("/api/analytics/delivery-trends")
def get_delivery_trends(
    db: Session = Depends(get_db),
):
    return analytics.delivery_trends(db)


@app.get("/api/analytics/top-vendors")
def get_top_vendors(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return analytics.top_vendors(db, limit)


@app.get("/api/analytics/risk-distribution")
def get_risk_distribution(
    db: Session = Depends(get_db),
):
    return analytics.risk_distribution(db)


@app.get("/api/analytics/late-orders")
def get_late_orders(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return analytics.late_orders(db, limit)
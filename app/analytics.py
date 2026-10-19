"""Optimized vendor analytics for VendorPulse Management.

Uses grouped SQL queries instead of querying orders and reviews once per vendor.
The risk score remains a transparent heuristic, not a trained ML model.
"""
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Vendor, PurchaseOrder, PurchaseOrderItem, Review
from collections import Counter , defaultdict


def vendor_performance(db: Session):
    """Return the same vendor-performance fields with a small number of queries."""
    vendors = db.query(Vendor).order_by(Vendor.vendor_id).all()

    # Query 1: one grouped query for item counts and spend per vendor.
    item_rows = (
        db.query(
            PurchaseOrderItem.vendor_id,
            func.count(func.distinct(PurchaseOrderItem.order_id)).label("order_count"),
            func.coalesce(
                func.sum(
                    func.coalesce(PurchaseOrderItem.item_price, 0.0)
                    + func.coalesce(PurchaseOrderItem.freight_value, 0.0)
                ),
                0.0,
            ).label("sales_and_freight_value"),
        )
        .group_by(PurchaseOrderItem.vendor_id)
        .all()
    )
    item_stats = {
        row.vendor_id: {
            "order_count": int(row.order_count or 0),
            "sales_and_freight_value": float(row.sales_and_freight_value or 0.0),
        }
        for row in item_rows
    }

    # Query 2: fetch each vendor/order pair once. We process delivery dates in
    # Python so date arithmetic works consistently with PostgreSQL and SQLite.
    vendor_order_rows = (
        db.query(
            PurchaseOrderItem.vendor_id,
            PurchaseOrder.order_id,
            PurchaseOrder.purchase_timestamp,
            PurchaseOrder.delivered_customer_date,
            PurchaseOrder.estimated_delivery_date,
        )
        .join(PurchaseOrder, PurchaseOrder.order_id == PurchaseOrderItem.order_id)
        .distinct()
        .all()
    )
    delivery_stats = defaultdict(
        lambda: {"completed": 0, "on_time": 0, "duration_total": 0.0, "duration_count": 0}
    )
    vendor_order_pairs = set()
    for row in vendor_order_rows:
        vendor_id = row.vendor_id
        vendor_order_pairs.add((vendor_id, row.order_id))
        stats = delivery_stats[vendor_id]
        delivered = row.delivered_customer_date
        estimated = row.estimated_delivery_date
        purchased = row.purchase_timestamp

        if delivered is not None and estimated is not None:
            stats["completed"] += 1
            if delivered <= estimated:
                stats["on_time"] += 1
        if delivered is not None and purchased is not None:
            stats["duration_total"] += (delivered - purchased).total_seconds() / 86400
            stats["duration_count"] += 1

    # Query 3: average review score per vendor. The subquery prevents an order
    # containing multiple items from multiplying the same vendor/order pair.
    vendor_order_subquery = (
        db.query(
            PurchaseOrderItem.vendor_id.label("vendor_id"),
            PurchaseOrderItem.order_id.label("order_id"),
        )
        .distinct()
        .subquery()
    )
    review_rows = (
        db.query(
            vendor_order_subquery.c.vendor_id,
            func.avg(Review.review_score).label("average_review_score"),
        )
        .join(Review, Review.order_id == vendor_order_subquery.c.order_id)
        .filter(Review.review_score.isnot(None))
        .group_by(vendor_order_subquery.c.vendor_id)
        .all()
    )
    review_stats = {
        row.vendor_id: float(row.average_review_score)
        for row in review_rows
        if row.average_review_score is not None
    }

    results = []
    for vendor in vendors:
        vendor_id = vendor.vendor_id
        item_stat = item_stats.get(
            vendor_id,
            {"order_count": 0, "sales_and_freight_value": 0.0},
        )
        delivery = delivery_stats.get(vendor_id)
        if delivery is None:
            delivery = {"completed": 0, "on_time": 0, "duration_total": 0.0, "duration_count": 0}

        completed = delivery["completed"]
        on_time_pct = round(100.0 * delivery["on_time"] / completed, 2) if completed else None
        avg_days = (
            round(delivery["duration_total"] / delivery["duration_count"], 2)
            if delivery["duration_count"]
            else None
        )
        avg_review_raw = review_stats.get(vendor_id)
        avg_review = round(avg_review_raw, 2) if avg_review_raw is not None else None

        # Same documented heuristic as the starter version; this is not ML.
        risk = (
            round(
                max(
                    0,
                    min(
                        100,
                        0.7 * (100 - on_time_pct)
                        + 0.3 * ((5 - (avg_review or 3)) * 25),
                    ),
                ),
                2,
            )
            if on_time_pct is not None
            else None
        )
        tier = (
            "Insufficient Data"
            if risk is None
            else "High"
            if risk >= 60
            else "Medium"
            if risk >= 30
            else "Low"
        )

        results.append(
            {
                "vendor_id": vendor_id,
                "city": vendor.city,
                "state": vendor.state,
                "order_count": item_stat["order_count"],
                "sales_and_freight_value": round(item_stat["sales_and_freight_value"], 2),
                "completed_orders_with_dates": completed,
                "on_time_delivery_pct": on_time_pct,
                "average_delivery_days": avg_days,
                "average_review_score": avg_review,
                "risk_score": risk,
                "risk_tier": tier,
            }
        )

    return results
def vendor_scorecard(db: Session, vendor_id: str):
    rows = vendor_performance(db)

    for row in rows:
        if row["vendor_id"] == vendor_id:
            return row

    return None
def top_vendors(db: Session, limit: int = 10):
    rows = vendor_performance(db)

    eligible = [
        row for row in rows
        if row["on_time_delivery_pct"] is not None
    ]

    eligible.sort(
        key=lambda row: (
            row["on_time_delivery_pct"],
            row["average_review_score"]
            if row["average_review_score"] is not None else -1,
            row["order_count"],
        ),
        reverse=True,
    )

    return [
        {**row, "rank": index + 1}
        for index, row in enumerate(eligible[:limit])
    ]
def risk_distribution(db: Session):
    rows = vendor_performance(db)
    counts = Counter(row["risk_tier"] for row in rows)

    return {
        "total_vendors": len(rows),
        "risk_distribution": [
            {
                "risk_tier": tier,
                "vendor_count": counts.get(tier, 0),
            }
            for tier in (
                "High",
                "Medium",
                "Low",
                "Insufficient Data",
            )
        ],
    }
def delivery_trends(db: Session):
    rows = (
        db.query(
            PurchaseOrderItem.vendor_id,
            PurchaseOrder.order_id,
            PurchaseOrder.delivered_customer_date,
            PurchaseOrder.estimated_delivery_date,
        )
        .join(
            PurchaseOrder,
            PurchaseOrder.order_id == PurchaseOrderItem.order_id,
        )
        .filter(
            PurchaseOrder.delivered_customer_date.isnot(None)
        )
        .distinct()
        .all()
    )

    monthly = defaultdict(lambda: {
        "delivered_orders": 0,
        "on_time_orders": 0,
        "late_orders": 0,
        "orders_without_estimate": 0,
    })

    seen = set()

    for row in rows:
        key = (row.vendor_id, row.order_id)

        if key in seen:
            continue

        seen.add(key)
        month = row.delivered_customer_date.strftime("%Y-%m")
        stats = monthly[month]
        stats["delivered_orders"] += 1

        if row.estimated_delivery_date is None:
            stats["orders_without_estimate"] += 1
        elif row.delivered_customer_date <= row.estimated_delivery_date:
            stats["on_time_orders"] += 1
        else:
            stats["late_orders"] += 1

    return [
        {"month": month, **monthly[month]}
        for month in sorted(monthly)
    ]

def late_orders(db: Session, limit: int = 100):
    rows = (
        db.query(
            PurchaseOrderItem.vendor_id,
            PurchaseOrder.order_id,
            PurchaseOrder.purchase_timestamp,
            PurchaseOrder.delivered_customer_date,
            PurchaseOrder.estimated_delivery_date,
        )
        .join(
            PurchaseOrder,
            PurchaseOrder.order_id == PurchaseOrderItem.order_id,
        )
        .filter(
            PurchaseOrder.delivered_customer_date.isnot(None),
            PurchaseOrder.estimated_delivery_date.isnot(None),
        )
        .distinct()
        .all()
    )

    result = []
    seen = set()

    for row in rows:
        key = (row.vendor_id, row.order_id)

        if key in seen:
            continue

        seen.add(key)

        if row.delivered_customer_date > row.estimated_delivery_date:
            result.append({
                "vendor_id": row.vendor_id,
                "order_id": row.order_id,
                "purchase_timestamp": (
                    row.purchase_timestamp.isoformat()
                    if row.purchase_timestamp else None
                ),
                "estimated_delivery_date": (
                    row.estimated_delivery_date.isoformat()
                ),
                "delivered_customer_date": (
                    row.delivered_customer_date.isoformat()
                ),
                "delay_days": (
                    row.delivered_customer_date
                    - row.estimated_delivery_date
                ).total_seconds() / 86400,
            })

    result.sort(
        key=lambda row: row["delay_days"],
        reverse=True,
    )

    return result[:limit]

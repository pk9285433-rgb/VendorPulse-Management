from pathlib import Path
import pandas as pd
from app.database import Base, engine, SessionLocal
from app.models import Vendor, PurchaseOrder, PurchaseOrderItem, Review

RAW = Path("data/raw")
def csv(name):
    path = RAW / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Download Olist CSVs and place them in data/raw/.")
    return pd.read_csv(path)
def dt(value):
    return pd.to_datetime(value, errors="coerce")

def main():
    Base.metadata.create_all(bind=engine)
    sellers = csv("olist_sellers_dataset.csv").drop_duplicates("seller_id")
    orders = csv("olist_orders_dataset.csv").drop_duplicates("order_id")
    items = csv("olist_order_items_dataset.csv")
    reviews = csv("olist_order_reviews_dataset.csv").drop_duplicates("review_id")
    date_cols = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
                 "order_delivered_customer_date", "order_estimated_delivery_date"]
    for c in date_cols: orders[c] = dt(orders[c])
    for c in ["review_creation_date", "review_answer_timestamp"]: reviews[c] = dt(reviews[c])
    db = SessionLocal()
    try:
        # Fresh-demo import: replace old imported records.
        db.query(Review).delete()
        db.query(PurchaseOrderItem).delete()
        db.query(PurchaseOrder).delete()
        db.query(Vendor).delete()
        db.commit()
        db.add_all([Vendor(vendor_id=str(r.seller_id),
            zip_code_prefix=int(r.seller_zip_code_prefix) if pd.notna(r.seller_zip_code_prefix) else None,
            city=str(r.seller_city) if pd.notna(r.seller_city) else None,
            state=str(r.seller_state) if pd.notna(r.seller_state) else None)
            for r in sellers.itertuples(index=False)])
        db.commit()
        db.add_all([PurchaseOrder(order_id=str(r.order_id),
            customer_id=str(r.customer_id) if pd.notna(r.customer_id) else None,
            order_status=str(r.order_status) if pd.notna(r.order_status) else None,
            purchase_timestamp=r.order_purchase_timestamp.to_pydatetime() if pd.notna(r.order_purchase_timestamp) else None,
            approved_at=r.order_approved_at.to_pydatetime() if pd.notna(r.order_approved_at) else None,
            delivered_carrier_date=r.order_delivered_carrier_date.to_pydatetime() if pd.notna(r.order_delivered_carrier_date) else None,
            delivered_customer_date=r.order_delivered_customer_date.to_pydatetime() if pd.notna(r.order_delivered_customer_date) else None,
            estimated_delivery_date=r.order_estimated_delivery_date.to_pydatetime() if pd.notna(r.order_estimated_delivery_date) else None)
            for r in orders.itertuples(index=False)])
        db.commit()
        valid_orders = {x[0] for x in db.query(PurchaseOrder.order_id).all()}
        valid_vendors = {x[0] for x in db.query(Vendor.vendor_id).all()}
        items = items[items.order_id.astype(str).isin(valid_orders) & items.seller_id.astype(str).isin(valid_vendors)]
        db.add_all([PurchaseOrderItem(order_id=str(r.order_id), vendor_id=str(r.seller_id),
            product_id=str(r.product_id) if pd.notna(r.product_id) else None,
            item_price=float(r.price) if pd.notna(r.price) else None,
            freight_value=float(r.freight_value) if pd.notna(r.freight_value) else None)
            for r in items.itertuples(index=False)])
        db.commit()
        valid_orders = {x[0] for x in db.query(PurchaseOrder.order_id).all()}
        reviews = reviews[reviews.order_id.astype(str).isin(valid_orders)]
        db.add_all([Review(review_id=str(r.review_id), order_id=str(r.order_id),
            review_score=int(r.review_score) if pd.notna(r.review_score) else None,
            review_creation_date=r.review_creation_date.to_pydatetime() if pd.notna(r.review_creation_date) else None,
            review_answer_timestamp=r.review_answer_timestamp.to_pydatetime() if pd.notna(r.review_answer_timestamp) else None)
            for r in reviews.itertuples(index=False)])
        db.commit()
        print("Import complete:",
              "vendors=", db.query(Vendor).count(),
              "orders=", db.query(PurchaseOrder).count(),
              "items=", db.query(PurchaseOrderItem).count(),
              "reviews=", db.query(Review).count())
    finally:
        db.close()

if __name__ == "__main__":
    main()

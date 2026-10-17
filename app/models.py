from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from .database import Base

class Vendor(Base):
    __tablename__ = "vendors"
    vendor_id = Column(String, primary_key=True, index=True)
    zip_code_prefix = Column(Integer)
    city = Column(String, index=True)
    state = Column(String)
    items = relationship("PurchaseOrderItem", back_populates="vendor")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    order_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    order_status = Column(String, index=True)
    purchase_timestamp = Column(DateTime)
    approved_at = Column(DateTime)
    delivered_carrier_date = Column(DateTime)
    delivered_customer_date = Column(DateTime)
    estimated_delivery_date = Column(DateTime)
    items = relationship("PurchaseOrderItem", back_populates="order")
    review = relationship("Review", back_populates="order", uselist=False)

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("purchase_orders.order_id"), nullable=False, index=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    product_id = Column(String, index=True)
    item_price = Column(Float)
    freight_value = Column(Float)
    order = relationship("PurchaseOrder", back_populates="items")
    vendor = relationship("Vendor", back_populates="items")

class Review(Base):
    __tablename__ = "reviews"
    review_id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("purchase_orders.order_id"), nullable=False, index=True)
    review_score = Column(Integer)
    review_creation_date = Column(DateTime)
    review_answer_timestamp = Column(DateTime)
    order = relationship("PurchaseOrder", back_populates="review")

Index("ix_items_vendor_order", PurchaseOrderItem.vendor_id, PurchaseOrderItem.order_id)

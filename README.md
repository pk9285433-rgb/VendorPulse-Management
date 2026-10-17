# VendorPulse Management

Starter project: FastAPI + SQLAlchemy + PostgreSQL/Supabase + Streamlit.

## Dataset
Download the Olist Brazilian E-Commerce dataset:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
Put the CSVs in `data/raw/`. Required files:
- olist_sellers_dataset.csv
- olist_orders_dataset.csv
- olist_order_items_dataset.csv
- olist_order_reviews_dataset.csv

Olist is an anonymized e-commerce seller dataset, not industrial procurement data. This project models sellers as vendors. Do not claim it contains real contractual compliance or defect-rate labels.

## Setup (Python 3.10+)
```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```
Copy `.env.example` to `.env`. SQLite works locally by default. For Supabase, set `DATABASE_URL` to your PostgreSQL connection URL; never commit `.env`.

Import the CSVs:
```bash
python -m etl.load_olist
```
Start API:
```bash
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs

Start dashboard in another terminal:
```bash
streamlit run dashboard/Home.py
```

## Endpoints
- GET /health
- GET /api/vendors
- GET /api/vendors/{vendor_id}
- GET /api/analytics/summary
- GET /api/analytics/vendor-performance
- GET /api/analytics/vendor-risks

Risk scoring is a transparent heuristic for demonstration, not a trained or validated ML model. Validate results before business use.

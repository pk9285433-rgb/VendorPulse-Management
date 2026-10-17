import os, requests, pandas as pd, streamlit as st, plotly.express as px
st.set_page_config(page_title="VendorPulse Management", page_icon="📦", layout="wide")
API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
st.title("📦 VendorPulse Management")
st.caption("Vendor delivery performance, order value, customer reviews, and explainable risk indicators.")

def get(path, params=None):
    try:
        r = requests.get(API + path, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"Cannot reach API at {API}. Start FastAPI first. Details: {e}")
        st.stop()

s = get("/api/analytics/summary")
cols = st.columns(4)
cols[0].metric("Vendors", f"{s['vendor_count']:,}")
cols[1].metric("Orders", f"{s['order_count']:,}")
cols[2].metric("Order items", f"{s['order_item_count']:,}")
cols[3].metric("Avg on-time delivery", f"{s['average_on_time_delivery_pct']}%" if s["average_on_time_delivery_pct"] is not None else "N/A")
data = get("/api/analytics/vendor-performance", {"limit": 1000})
df = pd.DataFrame(data.get("items", []))
st.subheader("Vendor performance")
if df.empty:
    st.info("No data loaded. Add Olist CSVs to data/raw and run python -m etl.load_olist.")
else:
    a, b = st.columns(2)
    valid = df.dropna(subset=["on_time_delivery_pct"])
    if not valid.empty:
        a.plotly_chart(px.bar(valid.nlargest(15, "order_count"), x="vendor_id", y="on_time_delivery_pct",
                              title="On-time delivery % (top vendors by order volume)"), use_container_width=True)
    known = df.dropna(subset=["risk_score"])
    if not known.empty:
        b.plotly_chart(px.histogram(known, x="risk_score", color="risk_tier", title="Rule-based risk score"), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
st.subheader("Vendor risks")
risks = pd.DataFrame(get("/api/analytics/vendor-risks", {"limit": 1000}).get("items", []))
if not risks.empty:
    tier = st.selectbox("Risk tier", ["All", "High", "Medium", "Low", "Insufficient Data"])
    if tier != "All": risks = risks[risks.risk_tier == tier]
    st.dataframe(risks, use_container_width=True, hide_index=True)
st.caption("Risk is a transparent heuristic, not a validated ML prediction. Review data limitations before business use.")

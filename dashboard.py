import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from streamlit_autorefresh import st_autorefresh
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

DB = "data.db"

# -------------------------
# Auto refresh
# -------------------------
st_autorefresh(interval=10000, limit=None, key="refresh")

# -------------------------
# Load data
# -------------------------
def load_data():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT * FROM posts
        ORDER BY scraped_at DESC, id DESC
        LIMIT 400
    """, conn)
    conn.close()
    return df


df = load_data()

if df.empty:
    st.warning("No data")
    st.stop()

df["scraped_at"] = pd.to_datetime(df["scraped_at"], unit="s")

# -------------------------
# Embedding model
# -------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

texts = df["title"].fillna("").tolist()
embeddings = model.encode(texts)

# -------------------------
# Semantic clustering
# -------------------------
n_clusters = min(5, len(df))
kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
df["cluster"] = kmeans.fit_predict(embeddings)

# -------------------------
# Simple scoring
# -------------------------
def score(text, source):
    text = text.lower()
    score = 0

    keywords = ["ai", "hack", "security", "startup", "funding", "launch"]

    for k in keywords:
        if k in text:
            score += 2

    if source == "github":
        score += 1

    return score

df["score"] = df.apply(lambda r: score(r["title"], r["source"]), axis=1)

# -------------------------
# Anomaly detection (z-score)
# -------------------------
mean = df["score"].mean()
std = df["score"].std() if df["score"].std() > 0 else 1

df["zscore"] = (df["score"] - mean) / std

df["anomaly"] = df["zscore"] > 2.0

# -------------------------
# ALERT SYSTEM
# -------------------------
alerts = df[df["anomaly"]]

if not alerts.empty:
    st.error(f"⚠️ {len(alerts)} anomaly signals detected")

    for _, row in alerts.head(5).iterrows():
        st.write(f"🚨 {row['title']} ({row['source']})")

# -------------------------
# Sidebar filters
# -------------------------
st.sidebar.title("Filters")

sources = df["source"].unique().tolist()
selected_sources = st.sidebar.multiselect("Sources", sources, default=sources)

clusters = df["cluster"].unique().tolist()
selected_clusters = st.sidebar.multiselect("Clusters", clusters, default=clusters)

min_score = st.sidebar.slider("Min score", 0, 10, 0)

df = df[
    (df["source"].isin(selected_sources)) &
    (df["cluster"].isin(selected_clusters)) &
    (df["score"] >= min_score)
]

# -------------------------
# Sort
# -------------------------
df = df.sort_values(["zscore", "score"], ascending=False)

# -------------------------
# UI
# -------------------------
st.title("Signal Intelligence Engine")

st.subheader("Cluster Overview")

st.dataframe(df[["cluster", "score", "zscore", "title", "source"]], width="stretch")

st.subheader("Semantic Clusters (Trend Groups)")

for c in df["cluster"].unique():
    st.markdown(f"### Cluster {c}")
    st.write(df[df["cluster"] == c][["title", "source"]].head(5))

st.subheader("Anomaly Feed")

st.dataframe(df[df["anomaly"]][["title", "source", "zscore", "score"]], width="stretch")

st.subheader("Full Signal Feed")

st.dataframe(df[["title", "source", "cluster", "score", "scraped_at"]], width="stretch")

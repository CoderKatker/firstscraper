import streamlit as st
import sqlite3
import pandas as pd
import time
import re
from collections import Counter
from streamlit_autorefresh import st_autorefresh

DB = "data.db"

# --------------------------
# Auto refresh
# --------------------------
st_autorefresh(interval=30000, limit=None, key="refresh")

# --------------------------
# DB load
# --------------------------
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def load_data():
    conn = get_conn()

    df = pd.read_sql_query("""
        SELECT * FROM posts
        ORDER BY scraped_at DESC, id DESC
        LIMIT 500
    """, conn)

    conn.close()
    return df

# --------------------------
# Scoring system (multi-source aware)
# --------------------------
def score(text, source):
    text = text.lower()
    score = 0

    keywords = [
        "ai", "llm", "gpt", "model", "agent",
        "security", "hack", "vulnerability",
        "startup", "funding", "launch",
        "paper", "research", "release"
    ]

    for k in keywords:
        if k in text:
            score += 2

    # source weighting (signal quality bias)
    if source in ["hackernews", "github", "arxiv"]:
        score += 1

    return score

# --------------------------
# Emerging topic detection
# --------------------------
def extract_phrases(text):
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())

    stop = {
        "the","and","for","with","from","that","this","are","was",
        "have","has","not","you","your","new","how","why","what",
        "com","org","net","github","browser","text"
    }

    words = [w for w in words if w not in stop]

    phrases = []

    # bigrams
    for i in range(len(words)-1):
        phrases.append(words[i] + " " + words[i+1])

    # trigrams
    for i in range(len(words)-2):
        phrases.append(words[i] + " " + words[i+1] + " " + words[i+2])

    return phrases


def detect_emerging_topics(df):
    if len(df) < 30:
        return []

    df = df.sort_values("scraped_at", ascending=False)

    recent = df.head(80)
    older = df.iloc[80:300]

    recent_counts = Counter()
    older_counts = Counter()

    for t in recent["title"]:
        recent_counts.update(extract_phrases(t))

    for t in older["title"]:
        older_counts.update(extract_phrases(t))

    scored = []

    for phrase, rcount in recent_counts.items():
        ocount = older_counts.get(phrase, 0)

        if rcount < 2:
            continue

        velocity = rcount / (1 + ocount)

        scored.append((phrase, round(velocity, 2), rcount, ocount))

    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:15]

# --------------------------
# UI
# --------------------------
st.title("Multi-Source Signal Intelligence Dashboard")

df = load_data()

if df.empty:
    st.warning("No data available. Run ingest.py first.")
    st.stop()

df["scraped_at"] = pd.to_datetime(df["scraped_at"], unit="s")

# --------------------------
# Apply scoring
# --------------------------
df["score"] = df.apply(lambda r: score(r["title"], r["source"]), axis=1)

# --------------------------
# Sidebar filters
# --------------------------
st.sidebar.title("Filters")

sources = sorted(df["source"].unique().tolist())

selected_sources = st.sidebar.multiselect(
    "Sources",
    sources,
    default=sources
)

min_score = st.sidebar.slider("Min Score", 0, 10, 0)

search = st.sidebar.text_input("Search")

df = df[df["source"].isin(selected_sources)]
df = df[df["score"] >= min_score]

if search:
    df = df[df["title"].str.contains(search, case=False, na=False)]

# --------------------------
# Metrics
# --------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Items", len(df))

with col2:
    st.metric("Sources Active", df["source"].nunique())

with col3:
    st.metric("Avg Score", round(df["score"].mean(), 2))

# --------------------------
# Source distribution
# --------------------------
st.subheader("Source Distribution")

st.bar_chart(df["source"].value_counts())

# --------------------------
# Emerging topics
# --------------------------
st.subheader("Emerging Topics (Velocity Detection)")

topics = detect_emerging_topics(df)

if topics:
    topic_df = pd.DataFrame(
        topics,
        columns=["Phrase", "Velocity", "Recent Count", "Baseline Count"]
    )
    st.dataframe(topic_df, width="stretch")
else:
    st.info("Not enough data yet for trend detection.")

# --------------------------
# Main feed
# --------------------------
st.subheader("Unified Signal Feed")

df = df.sort_values(["score", "scraped_at"], ascending=[False, False])

st.dataframe(
    df[["source", "score", "title", "link", "scraped_at"]],
    width="stretch"
)

# --------------------------
# Cluster placeholder (if you added embeddings later)
# --------------------------
if "cluster" in df.columns:
    st.subheader("Clusters")

    for c in sorted(df["cluster"].unique()):
        st.markdown(f"### Cluster {c}")
        st.write(df[df["cluster"] == c][["source", "title", "score"]].head(5))

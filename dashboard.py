import math
import streamlit as st
import sqlite3
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
from streamlit_autorefresh import st_autorefresh
from collections import Counter
import re

DB = "data.db"
SCRAPE_INTERVAL_SECONDS = 600   # 10 minutes
AUTO_REFRESH_MS = 30000        # page refresh every 30 seconds

# --------------------------
# Auto refresh
# --------------------------
st_autorefresh(interval=AUTO_REFRESH_MS, limit=None, key="refresh")

# --------------------------
# DB setup
# --------------------------
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        title TEXT,
        link TEXT,
        meta TEXT,
        scraped_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Remove duplicates, keep newest row
    cur.execute("""
    DELETE FROM posts
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM posts
        GROUP BY source, link
    )
    """)

    # Create unique index after cleanup
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_post
    ON posts(source, link)
    """)

    conn.commit()
    conn.close()

# --------------------------
# State helpers
# --------------------------
def get_state(key, default=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_state WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default

def set_state(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO app_state(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

# --------------------------
# Scraper
# --------------------------
def scrape_hn():
    url = "https://news.ycombinator.com/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        html = requests.get(url, headers=headers, timeout=10).text
    except Exception:
        return 0

    soup = BeautifulSoup(html, "html.parser")

    titles = soup.select(".titleline")
    subtexts = soup.select(".subtext")

    conn = get_conn()
    cur = conn.cursor()

    inserted = 0

    for i in range(min(len(titles), len(subtexts))):
        title = titles[i].get_text(strip=True)
        link = titles[i].find("a")["href"] if titles[i].find("a") else ""
        meta = subtexts[i].get_text(" ", strip=True)

        try:
            cur.execute("""
                INSERT INTO posts (source, title, link, meta, scraped_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("hackernews", title, link, meta, time.time()))
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    return inserted

# --------------------------
# Controlled scrape
# --------------------------
def maybe_scrape():
    last = float(get_state("last_scrape", "0"))
    now = time.time()

    if now - last >= SCRAPE_INTERVAL_SECONDS:
        count = scrape_hn()
        set_state("last_scrape", now)
        return count
    return 0

# --------------------------
# Data loading
# --------------------------
@st.cache_data(ttl=60)
def load_data():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT * FROM posts
        ORDER BY scraped_at DESC, id DESC
        LIMIT 300
    """, conn)
    conn.close()
    return df

# --------------------------
# Keyword trends
# --------------------------

def extract_phrases(text):
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())

    stop = {
        "the","and","for","with","from","that","this","are","was",
        "have","has","not","you","your","new","how","why","what"
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
    if len(df) < 20:
        return []

    df = df.sort_values("scraped_at", ascending=False)

    recent = df.head(50)
    older = df.iloc[50:250]

    recent_counts = Counter()
    older_counts = Counter()

    for title in recent["title"]:
        recent_counts.update(extract_phrases(title))

    for title in older["title"]:
        older_counts.update(extract_phrases(title))

    scored = []

    for phrase, recent_count in recent_counts.items():
        old_count = older_counts.get(phrase, 0)

        # velocity score
        score = recent_count / (1 + old_count)

        # require multiple recent mentions
        if recent_count >= 2:
            scored.append((phrase, round(score, 2), recent_count, old_count))

    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:15]
# --------------------------
# Startup
# --------------------------
init_db()
new_rows = maybe_scrape()
df = load_data()

# --------------------------
# UI
# --------------------------
st.title("Hacker News Signal Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Rows Loaded", len(df))

with col2:
    st.metric("New Rows Added", new_rows)

with col3:
    last_scrape = float(get_state("last_scrape", "0"))
    mins = int((time.time() - last_scrape) / 60)
    st.metric("Last Scrape", f"{mins} min ago")

if df.empty:
    st.warning("No data available.")
    st.stop()

df["scraped_at"] = pd.to_datetime(df["scraped_at"], unit="s")

# --------------------------
# Search
# --------------------------
query = st.text_input("Search titles")

if query:
    df = df[df["title"].str.contains(query, case=False, na=False)]

# --------------------------
# Trending keywords
# --------------------------

st.subheader("Emerging Topics (Velocity-Based)")

top_words = detect_emerging_topics(df)

if top_words:
    trend_df = pd.DataFrame(
        top_words,
        columns=["Phrase", "Velocity Score", "Recent Count", "Baseline Count"]
    )
    st.dataframe(trend_df, width="stretch")
else:
    st.info("Not enough data yet to compute trends.")

# --------------------------
# Feed
# --------------------------
st.subheader("Latest Feed")

st.dataframe(
    df[["title", "link", "scraped_at"]],
    width="stretch"
)

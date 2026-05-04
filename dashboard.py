import streamlit as st
import sqlite3
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
from streamlit_autorefresh import st_autorefresh

DB = "data.db"

# --------------------------
# Auto refresh
# --------------------------
st_autorefresh(interval=10000, limit=None, key="refresh")

# --------------------------
# Init DB
# --------------------------
def init_db():
    conn = sqlite3.connect(DB)
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

    conn.commit()
    conn.close()

# --------------------------
# Scrape Hacker News
# --------------------------
def scrape_hn():
    url = "https://news.ycombinator.com/"
    headers = {"User-Agent": "Mozilla/5.0"}

    html = requests.get(url, headers=headers, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    titles = soup.select(".titleline")
    subtexts = soup.select(".subtext")

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for i in range(min(len(titles), len(subtexts))):
        title = titles[i].get_text(strip=True)
        link = titles[i].find("a")["href"] if titles[i].find("a") else ""
        meta = subtexts[i].get_text(" ", strip=True)

        cur.execute("""
            INSERT INTO posts (source, title, link, meta, scraped_at)
            VALUES (?, ?, ?, ?, ?)
        """, ("hackernews", title, link, meta, time.time()))

    conn.commit()
    conn.close()

# --------------------------
# Load data
# --------------------------
def load_data():
    conn = sqlite3.connect(DB)

    df = pd.read_sql_query("""
        SELECT * FROM posts
        ORDER BY scraped_at DESC, id DESC
        LIMIT 100
    """, conn)

    conn.close()
    return df

# --------------------------
# Startup
# --------------------------
init_db()

# scrape on each refresh
scrape_hn()

df = load_data()

# --------------------------
# UI
# --------------------------
st.title("Live Hacker News Dashboard")

df["scraped_at"] = pd.to_datetime(df["scraped_at"], unit="s")

st.dataframe(
    df[["source", "title", "link", "scraped_at"]],
    width="stretch"
)

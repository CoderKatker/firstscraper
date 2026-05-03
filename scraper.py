import requests
from bs4 import BeautifulSoup
import sqlite3
import time

DB = "data.db"

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


def scrape_hackernews():
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


if __name__ == "__main__":
    init_db()
    scrape_hackernews()
    print("Scraped HN")

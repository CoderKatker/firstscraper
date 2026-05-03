import requests
from bs4 import BeautifulSoup
import sqlite3
import time

DB = "data.db"

def scrape_github():
    url = "https://github.com/trending"
    headers = {"User-Agent": "Mozilla/5.0"}

    html = requests.get(url, headers=headers, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    repos = soup.select("h2 a")

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for repo in repos:
        title = repo.get_text(strip=True)
        link = "https://github.com" + repo["href"]

        cur.execute("""
            INSERT INTO posts (source, title, link, meta, scraped_at)
            VALUES (?, ?, ?, ?, ?)
        """, ("github", title, link, "", time.time()))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    scrape_github()
    print("Scraped GitHub")

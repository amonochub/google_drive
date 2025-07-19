import sqlite3
from typing import Optional, List
from datetime import datetime
from models import Article

DB_PATH = 'sent.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sent (
            id TEXT PRIMARY KEY,
            published TEXT
        )
    ''')
    conn.commit()
    conn.close()

def is_sent(article_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM sent WHERE id=?', (article_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_sent(article_id: str, published: Optional[datetime]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    published_str = published.isoformat() if published else None
    c.execute('INSERT OR IGNORE INTO sent (id, published) VALUES (?, ?)', (article_id, published_str))
    conn.commit()
    conn.close()

def filter_new(articles: List[Article]) -> List[Article]:
    return [a for a in articles if not is_sent(a.id)]

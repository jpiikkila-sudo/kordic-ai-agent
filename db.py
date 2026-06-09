import sqlite3
import os

DB_PATH = "kordic.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    Initializes the local SQLite database schema.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create topics/articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            vertical TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            reference_age INTEGER DEFAULT 0, -- Age of references in days (freshness)
            wix_item_id TEXT, -- Wix CMS item ID if registered as draft
            local_file_path TEXT, -- Local path to output file
            status TEXT DEFAULT 'draft', -- 'draft' (in Wix or local file) or 'published' (live)
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("Local database initialized successfully.")

def is_duplicate(title: str) -> bool:
    """
    Checks if an article with the exact title already exists locally.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM articles WHERE title = ?", (title.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_article(title: str, vertical: str, content: str, category: str, reference_age: int) -> int:
    """
    Saves an article locally.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (title, vertical, content, category, reference_age, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
        """, (title.strip(), vertical.strip(), content.strip(), category.strip(), reference_age))
        conn.commit()
        last_row_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        last_row_id = -1 # Already exists
    finally:
        conn.close()
    return last_row_id

def mark_published(title: str, wix_item_id: str, local_file_path: str = None, status: str = 'draft'):
    """
    Marks an article with the corresponding Wix CMS Item ID, local file path, and status.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE articles 
        SET wix_item_id = ?, local_file_path = ?, status = ?, published_at = CURRENT_TIMESTAMP 
        WHERE title = ?
    """, (wix_item_id, local_file_path, status, title.strip()))
    conn.commit()
    conn.close()

def get_all_articles():
    """
    Returns all articles sorted by freshness (reference_age ascending) and grouped by category.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, vertical, category, reference_age, wix_item_id, local_file_path, status, created_at 
        FROM articles 
        ORDER BY category ASC, reference_age ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    articles = []
    for r in rows:
        articles.append({
            "title": r[0],
            "vertical": r[1],
            "category": r[2],
            "reference_age": r[3],
            "wix_item_id": r[4],
            "local_file_path": r[5],
            "status": r[6],
            "created_at": r[7]
        })
    return articles

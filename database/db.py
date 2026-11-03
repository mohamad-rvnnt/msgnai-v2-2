import sqlite3
from pathlib import Path

DB_PATH = Path.cwd() / "database" / "msgnai.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول تاریخچه مکالمات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # جدول فایل‌های دریافتی از تلگرام
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            file_path TEXT NOT NULL,
            chat_id TEXT,
            message_id TEXT,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # جدول پروژه‌های تحلیل‌شده
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            summary TEXT,
            report_path TEXT,
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # جدول وضعیت تلگرام (برای مدیریت Updateها و جلوگیری از پردازش تکراری)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)

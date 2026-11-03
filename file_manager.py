import sqlite3
from pathlib import Path
from database.db import DB_PATH

def list_stored_files(file_type=None, search_query=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = "SELECT id, file_name, file_type, file_size, file_path, received_at FROM telegram_files WHERE 1=1"
        params = []
        
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
            
        if search_query:
            query += " AND file_name LIKE ?"
            params.append(f"%{search_query}%")
            
        query += " ORDER BY received_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        files = []
        for row in rows:
            files.append({
                "id": row[0],
                "file_name": row[1],
                "file_type": row[2],
                "file_size": row[3],
                "file_path": row[4],
                "received_at": row[5]
            })
        return {"ok": True, "files": files}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def delete_stored_file(file_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM telegram_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"ok": False, "error": "فایل در پایگاه داده پیدا نشد."}
            
        file_path = Path(row[0])
        if file_path.exists():
            file_path.unlink()
            
        cursor.execute("DELETE FROM telegram_files WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()
        return {"ok": True, "message": "فایل با موفقیت حذف شد."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    res = list_stored_files()
    print("Stored files test result:", res)

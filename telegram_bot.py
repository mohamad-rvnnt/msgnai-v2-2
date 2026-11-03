import os
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path
from database.db import DB_PATH
import sqlite3

class TelegramBotHandler:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.allowed_chats = [
            c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()
        ]
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.storage_root = Path.cwd() / "memory" / "telegram_files"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        
        for sub in ("images", "documents", "code"):
            (self.storage_root / sub).mkdir(exist_ok=True)

    def get_last_update_id(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM telegram_state WHERE key = 'last_update_id'")
            row = cursor.fetchone()
            conn.close()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def set_last_update_id(self, update_id):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telegram_state (key, value) VALUES ('last_update_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = ?
            """, (str(update_id), str(update_id)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving update id: {e}")

    def send_message(self, chat_id, text):
        if not self.token:
            return False
        try:
            url = f"{self.base_url}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8")).get("ok", False)
        except Exception as e:
            print(f"Telegram send error: {e}")
            return False

    def get_file_info(self, file_id):
        try:
            url = f"{self.base_url}/getFile?file_id={file_id}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data["result"].get("file_path")
        except Exception as e:
            print(f"Get file info error: {e}")
        return None

    def download_telegram_file(self, file_path, dest_path):
        try:
            url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            with urllib.request.urlopen(url, timeout=30) as resp:
                with open(dest_path, "wb") as f:
                    f.write(resp.read())
            return True
        except Exception as e:
            print(f"Download file error: {e}")
            return False

    def save_file_to_db(self, file_name, file_type, file_size, file_path, chat_id, message_id):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telegram_files (file_name, file_type, file_size, file_path, chat_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file_name, file_type, file_size, str(file_path), str(chat_id), str(message_id)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database save file error: {e}")

    def poll_updates(self):
        if not self.token:
            print("Telegram Bot Token is not configured.")
            return

        last_update_id = self.get_last_update_id()
        print(f"Starting Telegram Bot Polling (Last Update ID: {last_update_id})...")

        try:
            url = f"{self.base_url}/getUpdates?offset={last_update_id + 1}&timeout=5"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("ok"):
                    return
                
                for update in data.get("result", []):
                    update_id = update["update_id"]
                    self.set_last_update_id(update_id)
                    
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue
                        
                    chat_id = str(message["chat"]["id"])
                    
                    # بررسی دسترسی چت مجاز
                    if self.allowed_chats and chat_id not in self.allowed_chats:
                        print(f"Unauthorized access attempt from chat_id: {chat_id}")
                        continue
                        
                    message_id = str(message.get("message_id"))
                    text = message.get("text", "")
                    
                    # پردازش فایل‌ها (عکس، سند، کد و غیره)
                    doc = message.get("document")
                    photo = message.get("photo")
                    
                    if doc:
                        file_id = doc["file_id"]
                        file_name = doc.get("file_name", f"doc_{int(time.time())}")
                        file_size = doc.get("file_size", 0)
                        
                        # دسته‌بندی نوع فایل
                        ext = Path(file_name).suffix.lower()
                        sub_folder = "code" if ext in (".py", ".js", ".json", ".sh", ".html", ".css", ".cpp", ".c", ".java") else "documents"
                        
                        tg_file_path = self.get_file_info(file_id)
                        if tg_file_path:
                            dest = self.storage_root / sub_folder / file_name
                            if self.download_telegram_file(tg_file_path, dest):
                                self.save_file_to_db(file_name, sub_folder, file_size, dest, chat_id, message_id)
                                self.send_message(chat_id, f"✅ فایل '{file_name}' با موفقیت دریافت و در حافظه ذخیره شد.")
                                
                    elif photo:
                        # بزرگ‌ترین سایز عکس
                        photo_item = photo[-1]
                        file_id = photo_item["file_id"]
                        file_name = f"image_{int(time.time())}.jpg"
                        file_size = photo_item.get("file_size", 0)
                        
                        tg_file_path = self.get_file_info(file_id)
                        if tg_file_path:
                            dest = self.storage_root / "images" / file_name
                            if self.download_telegram_file(tg_file_path, dest):
                                self.save_file_to_db(file_name, "images", file_size, dest, chat_id, message_id)
                                self.send_message(chat_id, f"✅ تصویر با موفقیت دریافت و در حافظه ذخیره شد.")
                                
                    elif text:
                        if text == "/start":
                            self.send_message(chat_id, "سلام! من ربات حافظه و فایل‌های MSGN AI 2.2 هستم. فایل‌ها و تصاویر خود را ارسال کنید تا در حافظه ذخیره شوند.")
                        else:
                            self.send_message(chat_id, f"پیام شما دریافت شد: {text}")

        except Exception as e:
            print(f"Polling error: {e}")

if __name__ == "__main__":
    bot = TelegramBotHandler()
    print("Telegram Handler initialized. (Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to start polling)")

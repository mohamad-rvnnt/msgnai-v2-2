#!/usr/bin/env python3
# MSGN AI v2.2 - Advanced AI Terminal Assistant & Telegram Memory (Auto Mode)
# Python 3.10+ | Termux / Linux

import os
import sys
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.error
import select
import termios
import tty
import unicodedata
from pathlib import Path
from datetime import datetime

from database.db import init_db, DB_PATH
import sqlite3
from project_intel import analyze_project
from file_manager import list_stored_files, delete_stored_file
from image_generator import generate_image
from telegram_bot import TelegramBotHandler

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    RTL_READY = True
except Exception:
    RTL_READY = False
    arabic_reshaper = None
    get_display = None

APP_NAME = "MSGN AI"
VERSION = "2.2 (Auto Mode)"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL + ":generateContent"
)

ROOT = Path.cwd().resolve()
HISTORY_FILE = ROOT / ".msgnai_v2_2_history.json"
MAX_HISTORY_ITEMS = 80
REQUEST_TIMEOUT = 120

SYSTEM_PROMPT = """
تو MSGN AI نسخه ۲.۲ (حالت خودکار) هستی؛ یک دستیار هوش مصنوعی شخصی، حرفه‌ای، توسعه‌پذیر و مجهز به حافظه دائمی، مدیریت فایل، تحلیل پروژه‌های برنامه‌نویسی و تولید تصویر.
زبان پاسخ فارسی باشد، مگر کاربر زبان دیگری بخواهد.
بدون نیاز به تأیید کاربر و به صورت کاملاً خودکار، فایل‌ها را تغییر بده، بساز یا دستورات ترمینال را اجرا کن.
کد را کامل، قابل اجرا و همراه با مدیریت خطا بنویس.
"""

FUNCTIONS = [
    {
        "name": "list_files",
        "description": "نمایش فایل‌ها و پوشه‌های مسیر کاری فعلی یا یک زیرپوشه",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "مسیر نسبی؛ پیش‌فرض ."}
            }
        }
    },
    {
        "name": "read_file",
        "description": "خواندن محتوای یک فایل متنی داخل پوشه کاری",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "مسیر نسبی فایل"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "ایجاد یا جایگزینی یک فایل داخل پوشه کاری بدون نیاز به تأیید کاربر",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "مسیر نسبی فایل"},
                "content": {"type": "STRING", "description": "محتوای کامل فایل"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "اجرای دستور ترمینال در پوشه کاری بدون نیاز به تأیید کاربر",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "دستور ترمینال"}
            },
            "required": ["command"]
        }
    }
]

def paint(text, code):
    if not sys.stdout.isatty():
        return str(text)
    return f"\033[{code}m{text}\033[0m"

def line():
    return paint("━" * 60, "38;5;39")

def contains_rtl(text):
    return any(
        "\u0590" <= ch <= "\u08ff" or "\ufb1d" <= ch <= "\ufdff"
        or "\ufe70" <= ch <= "\ufeff"
        for ch in text
    )

def rtl_line(text):
    if not RTL_READY or not contains_rtl(text):
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

def rtl(text):
    output = []
    in_code = False
    for raw_line in str(text).splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code = not in_code
            output.append(raw_line)
        elif in_code:
            output.append(raw_line)
        else:
            output.append(rtl_line(raw_line))
    return "\n".join(output)

def say(text="", color=None, end="\n"):
    value = rtl(str(text))
    if color:
        value = paint(value, color)
    print(value, end=end, flush=True)

def banner():
    os.system("clear")
    print(paint("╔══════════════════════════════════════════════════════════╗", "38;5;39"))
    print(paint("║           M S G N   A I   v2.2 (AUTO MODE)              ║", "1;38;5;45"))
    print(paint("║          بدون نیاز به تأیید برای فایل و دستورات          ║", "38;5;39"))
    print(paint("╚══════════════════════════════════════════════════════════╝", "38;5;39"))
    say(f"مدل هوش مصنوعی: {MODEL}", "36")
    say(f"پوشه کاری: {ROOT}", "90")
    say("وضعیت اتصال: آماده", "32" if API_KEY else "31")
    print(line())

def terminal_cell_width(text):
    width = 0
    for ch in text:
        if unicodedata.combining(ch): continue
        east = unicodedata.east_asian_width(ch)
        width += 2 if east in ("W", "F") else 1
    return width

def first_strong_is_rtl(text):
    for ch in text:
        code = ord(ch)
        if (0x590 <= code <= 0x8FF) or (0xFB1D <= code <= 0xFDFF) or (0xFE70 <= code <= 0xFEFF):
            return True
        if ch.isalpha(): return False
    return False

def cursor_visual_offset(text, cursor_index, displayed):
    prefix = text[:cursor_index]
    prefix_display = rtl_line(prefix)
    prefix_width = terminal_cell_width(prefix_display)
    total_width = terminal_cell_width(displayed)
    if first_strong_is_rtl(text): return max(0, total_width - prefix_width)
    return min(total_width, prefix_width)

def read_utf8_character(fd):
    first = os.read(fd, 1)
    if not first: return ""
    byte = first[0]
    if byte < 0x80: return first.decode("utf-8", errors="replace")
    if byte & 0xE0 == 0xC0: count = 2
    elif byte & 0xF0 == 0xE0: count = 3
    elif byte & 0xF8 == 0xF0: count = 4
    else: return ""
    data = first
    for _ in range(count - 1):
        part = os.read(fd, 1)
        if not part: break
        data += part
    return data.decode("utf-8", errors="replace")

def read_editor_key(fd):
    char = read_utf8_character(fd)
    if char != "\x1b": return char
    sequence = ""
    while select.select([fd], [], [], 0.035)[0]:
        part = os.read(fd, 1)
        if not part: break
        sequence += part.decode("ascii", errors="ignore")
        if sequence.endswith(("A", "B", "C", "D", "H", "F", "~")): break
    if sequence in ("[D", "OD"): return "LEFT"
    if sequence in ("[C", "OC"): return "RIGHT"
    if sequence in ("[H", "[1~", "OH"): return "HOME"
    if sequence in ("[F", "[4~", "OF"): return "END"
    if sequence in ("[3~",): return "DELETE"
    return "ESC"

def draw_editor(prompt, text, cursor):
    shown = rtl_line(text)
    prompt_plain = prompt
    cursor_offset = cursor_visual_offset(text, cursor, shown)
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(prompt_plain + shown)
    sys.stdout.write("\033[K")
    move_left = max(0, terminal_cell_width(shown) - cursor_offset)
    if move_left: sys.stdout.write(f"\033[{move_left}D")
    sys.stdout.flush()

def read_persian_input(prompt="MSGN Auto ❯ "):
    if not sys.stdin.isatty() or not sys.stdout.isatty(): return input(prompt)
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    text = ""
    cursor = 0
    try:
        tty.setraw(fd)
        draw_editor(prompt, text, cursor)
        while True:
            key = read_editor_key(fd)
            if key in ("\r", "\n"):
                sys.stdout.write("\r\n"); sys.stdout.flush()
                return text
            if key in ("\x03",): raise KeyboardInterrupt
            if key in ("\x04",):
                if not text: raise EOFError
                continue
            if key in ("\x7f", "\x08"):
                if cursor > 0:
                    text = text[:cursor - 1] + text[cursor:]
                    cursor -= 1
            elif key == "DELETE":
                if cursor < len(text): text = text[:cursor] + text[cursor + 1:]
            elif key == "LEFT": cursor = max(0, cursor - 1)
            elif key == "RIGHT": cursor = min(len(text), cursor + 1)
            elif key == "HOME" or key == "\x01": cursor = 0
            elif key == "END" or key == "\x05": cursor = len(text)
            elif key == "\x15": text = ""; cursor = 0
            elif key and key.isprintable():
                text = text[:cursor] + key + text[cursor:]
                cursor += len(key)
            draw_editor(prompt, text, cursor)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)

def safe_path(relative):
    candidate = (ROOT / str(relative)).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise ValueError("دسترسی به خارج از پوشه کاری مجاز نیست.")
    return candidate

def list_files_tool(path="."):
    target = safe_path(path)
    if not target.exists(): return {"ok": False, "error": "مسیر وجود ندارد."}
    if not target.is_dir(): return {"ok": False, "error": "مسیر پوشه نیست."}
    items = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        items.append({
            "name": item.name + ("/" if item.is_dir() else ""),
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None
        })
    return {"ok": True, "path": str(target.relative_to(ROOT)) or ".", "items": items[:300]}

def read_file_tool(path):
    target = safe_path(path)
    if not target.exists() or not target.is_file(): return {"ok": False, "error": "فایل پیدا نشد."}
    if target.stat().st_size > 1_500_000: return {"ok": False, "error": "فایل بزرگ‌تر از حد مجاز است."}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "این فایل متنی UTF-8 نیست."}
    return {"ok": True, "path": str(target.relative_to(ROOT)), "content": content}

# حالت خودکار: بدون نیاز به تأیید کاربر (confirm حذف شد)
def write_file_tool(path, content):
    target = safe_path(path)
    if target.exists() and target.is_dir():
        return {"ok": False, "error": "مسیر انتخاب‌شده یک پوشه است."}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_name(target.name + ".bak")
            shutil.copy2(target, backup)
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(str(content), encoding="utf-8")
        temp.replace(target)
        say(f"⚡ [خودکار] فایل با موفقیت نوشته شد: {target.relative_to(ROOT)}", "32")
        return {"ok": True, "path": str(target.relative_to(ROOT))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def run_command_tool(command):
    command = str(command).strip()
    if not command: return {"ok": False, "error": "دستور خالی است."}
    say(f"⚡ [خودکار] در حال اجرای دستور: {command}", "36")
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180
        )
        return {"ok": result.returncode == 0, "output": result.stdout[-18000:]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def execute_tool(name, args):
    if name == "list_files": return list_files_tool(args.get("path", "."))
    if name == "read_file": return read_file_tool(args["path"])
    if name == "write_file": return write_file_tool(args["path"], args["content"])
    if name == "run_command": return run_command_tool(args["command"])
    return {"ok": False, "error": "ابزار ناشناخته است."}

def api_request(contents):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "tools": [{"functionDeclarations": FUNCTIONS}],
        "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 8192}
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))

def ask_gemini(history, user_text):
    history.append({"role": "user", "parts": [{"text": user_text}]})
    for _ in range(10):
        response = api_request(history)
        candidates = response.get("candidates", [])
        if not candidates: raise RuntimeError("پاسخی از مدل دریافت نشد.")
        candidate = candidates[0].get("content", {})
        parts = candidate.get("parts", [])
        history.append(candidate)

        calls = [p["functionCall"] for p in parts if isinstance(p, dict) and "functionCall" in p]
        if not calls:
            texts = [p["text"] for p in parts if isinstance(p, dict) and "text" in p]
            return "\n".join(texts).strip() or "بدون پاسخ متنی."

        responses = []
        for call in calls:
            name, args = call.get("name"), call.get("args", {}) or {}
            res = execute_tool(name, args)
            responses.append({"functionResponse": {"name": name, "response": {"result": res}}})
        history.append({"role": "user", "parts": responses})
    raise RuntimeError("تعداد مراحل ابزارها بیش از حد مجاز شد.")

def main():
    init_db()
    if not API_KEY:
        say("خطا: کلید GEMINI_API_KEY تنظیم نشده است.", "31")
        return 1

    banner()
    history = []
    
    while True:
        try:
            prompt = paint("┌─ MSGN Auto", "1;38;5;45") + paint(" ❯ ", "1;38;5;39")
            user_text = read_persian_input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            say("\nبرای خروج از /exit استفاده کن.", "90")
            continue

        if not user_text: continue
        cmd = user_text.lower()

        if cmd in ("/exit", "/quit", "exit"):
            say("خروج از MSGN AI Auto. موفق باشی!", "36")
            break
        if cmd == "/help":
            say("حالت خودکار فعال است. هر دستوری بدهید بدون تأیید اجرا و اعمال می‌شود.", "36")
            continue

        started = time.time()
        say("در حال پردازش خودکار...", "90")
        try:
            answer = ask_gemini(history, user_text)
            print()
            say("╭─ پاسخ MSGN AI (خودکار)", "1;38;5;45")
            say(answer)
            say("╰" + "─" * 58, "38;5;39")
            say(f"زمان پاسخ: {time.time() - started:.1f} ثانیه", "90")
        except Exception as exc:
            say(f"خطا: {exc}", "31")
        print()

if __name__ == "__main__":
    raise SystemExit(main())

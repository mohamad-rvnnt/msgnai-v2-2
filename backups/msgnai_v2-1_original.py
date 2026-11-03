#!/usr/bin/env python3
# MSGN AI v2.1 - Gemini terminal coding assistant
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

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    RTL_READY = True
except Exception:
    RTL_READY = False
    arabic_reshaper = None
    get_display = None


APP_NAME = "MSGN AI"
VERSION = "2.1"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL + ":generateContent"
)

ROOT = Path.cwd().resolve()
HISTORY_FILE = ROOT / ".msgni_history.json"
MAX_HISTORY_ITEMS = 80
REQUEST_TIMEOUT = 120

SYSTEM_PROMPT = """
تو MSGN AI هستی؛ یک دستیار حرفه‌ای برنامه‌نویسی و مدیریت پروژه.
زبان پاسخ فارسی باشد، مگر کاربر زبان دیگری بخواهد.
قبل از تغییر فایل، محتوای مرتبط را بررسی کن.
برای تغییر فایل‌ها از ابزار write_file استفاده کن و هیچ‌وقت ادعا نکن
فایلی را تغییر داده‌ای مگر ابزار واقعاً موفق شده باشد.
برای اجرای دستور ترمینال از run_command استفاده کن؛ اجرای دستور فقط
پس از تأیید صریح کاربر انجام می‌شود.
دستورها را کوتاه، دقیق و متناسب با محیط فعلی کاربر بنویس.
مسیرهای فایل باید داخل پوشه کاری فعلی باشند.
اگر درخواست مبهم یا خطرناک است، ابتدا سؤال بپرس.
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
        "description": "ایجاد یا جایگزینی یک فایل داخل پوشه کاری؛ قبل از اجرا از کاربر تأیید می‌گیرد",
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
        "description": "اجرای دستور ترمینال در پوشه کاری؛ قبل از اجرا از کاربر تأیید می‌گیرد",
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
    """Shape and reorder Persian output, leaving code blocks unchanged."""
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
    print(paint("║                 M S G N   A I                           ║", "1;38;5;45"))
    print(paint("║          TERMINAL CODING ASSISTANT  •  v" + VERSION + "                 ║", "38;5;39"))
    print(paint("╚══════════════════════════════════════════════════════════╝", "38;5;39"))
    say(f"مدل: {MODEL}", "36")
    say(f"پوشه کاری: {ROOT}", "90")
    say("وضعیت اتصال: آماده بررسی", "32" if API_KEY else "31")
    if not RTL_READY:
        say("هشدار: بسته‌های نمایش فارسی نصب نیستند؛ pip install arabic-reshaper python-bidi==0.4.2", "33")
    say("برای راهنما /help را وارد کن.", "90")
    print(line())


def terminal_cell_width(text):
    """Approximate terminal display width, including Persian and emoji."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        east = unicodedata.east_asian_width(ch)
        width += 2 if east in ("W", "F") else 1
    return width


def first_strong_is_rtl(text):
    for ch in text:
        code = ord(ch)
        if (0x590 <= code <= 0x8FF) or (0xFB1D <= code <= 0xFDFF) or (0xFE70 <= code <= 0xFEFF):
            return True
        if ch.isalpha():
            return False
    return False


def cursor_visual_offset(text, cursor_index, displayed):
    """
    Estimate the visual cursor position after bidi reordering.
    The exact cursor mapping for mixed-direction Unicode is terminal-dependent.
    """
    prefix = text[:cursor_index]
    prefix_display = rtl_line(prefix)
    prefix_width = terminal_cell_width(prefix_display)
    total_width = terminal_cell_width(displayed)

    if first_strong_is_rtl(text):
        return max(0, total_width - prefix_width)
    return min(total_width, prefix_width)


def read_utf8_character(fd):
    first = os.read(fd, 1)
    if not first:
        return ""
    byte = first[0]
    if byte < 0x80:
        return first.decode("utf-8", errors="replace")
    if byte & 0xE0 == 0xC0:
        count = 2
    elif byte & 0xF0 == 0xE0:
        count = 3
    elif byte & 0xF8 == 0xF0:
        count = 4
    else:
        return "�"
    data = first
    for _ in range(count - 1):
        part = os.read(fd, 1)
        if not part:
            break
        data += part
    return data.decode("utf-8", errors="replace")


def read_editor_key(fd):
    char = read_utf8_character(fd)
    if char != "\x1b":
        return char

    # Read an ANSI escape sequence without blocking indefinitely.
    sequence = ""
    while select.select([fd], [], [], 0.035)[0]:
        part = os.read(fd, 1)
        if not part:
            break
        sequence += part.decode("ascii", errors="ignore")
        if sequence.endswith(("A", "B", "C", "D", "H", "F", "~")):
            break

    if sequence in ("[D", "OD"):
        return "LEFT"
    if sequence in ("[C", "OC"):
        return "RIGHT"
    if sequence in ("[H", "[1~", "OH"):
        return "HOME"
    if sequence in ("[F", "[4~", "OF"):
        return "END"
    if sequence in ("[3~",):
        return "DELETE"
    return "ESC"


def draw_editor(prompt, text, cursor):
    shown = rtl_line(text)
    prompt_plain = prompt
    prompt_width = terminal_cell_width(prompt_plain)
    cursor_offset = cursor_visual_offset(text, cursor, shown)
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(prompt_plain + shown)
    sys.stdout.write("\033[K")
    move_left = max(0, terminal_cell_width(shown) - cursor_offset)
    if move_left:
        sys.stdout.write(f"\033[{move_left}D")
    sys.stdout.flush()


def read_persian_input(prompt="MSGN ❯ "):
    """
    Small terminal line editor:
    - UTF-8 input
    - Persian shaping + bidi display while typing
    - Backspace/Delete, arrows, Home/End, Ctrl+A/E/U
    - Keeps the original logical text for Gemini
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return input(prompt)

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
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return text

            if key in ("\x03",):  # Ctrl+C
                raise KeyboardInterrupt

            if key in ("\x04",):  # Ctrl+D
                if not text:
                    raise EOFError
                continue

            if key in ("\x7f", "\x08"):  # Backspace
                if cursor > 0:
                    text = text[:cursor - 1] + text[cursor:]
                    cursor -= 1

            elif key == "DELETE":
                if cursor < len(text):
                    text = text[:cursor] + text[cursor + 1:]

            elif key == "LEFT":
                cursor = max(0, cursor - 1)

            elif key == "RIGHT":
                cursor = min(len(text), cursor + 1)

            elif key == "HOME" or key == "\x01":  # Home / Ctrl+A
                cursor = 0

            elif key == "END" or key == "\x05":  # End / Ctrl+E
                cursor = len(text)

            elif key == "\x15":  # Ctrl+U
                text = ""
                cursor = 0

            elif key == "\x17":  # Ctrl+W
                left = text[:cursor]
                stripped = left.rstrip()
                cut = len(stripped)
                while cut > 0 and not stripped[cut - 1].isspace():
                    cut -= 1
                text = text[:cut] + text[cursor:]
                cursor = cut

            elif key in ("ESC", "\x00"):
                pass

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


def list_files(path="."):
    target = safe_path(path)
    if not target.exists():
        return {"ok": False, "error": "مسیر وجود ندارد."}
    if not target.is_dir():
        return {"ok": False, "error": "مسیر پوشه نیست."}
    items = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        items.append({
            "name": item.name + ("/" if item.is_dir() else ""),
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None
        })
    return {"ok": True, "path": str(target.relative_to(ROOT)) or ".", "items": items[:300]}


def read_file(path):
    target = safe_path(path)
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "فایل پیدا نشد."}
    if target.stat().st_size > 1_500_000:
        return {"ok": False, "error": "فایل بزرگ‌تر از حد مجاز است."}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "این فایل متنی UTF-8 نیست."}
    return {"ok": True, "path": str(target.relative_to(ROOT)), "content": content}


def confirm(prompt):
    say(prompt, "33")
    answer = read_persian_input(paint("تأیید؟ [y/N]: ", "1;33")).strip().lower()
    return answer in ("y", "yes", "بله", "آره")


def write_file(path, content):
    target = safe_path(path)
    if target.exists() and target.is_dir():
        return {"ok": False, "error": "مسیر انتخاب‌شده یک پوشه است."}
    preview = str(content)
    say(f"درخواست نوشتن فایل: {target.relative_to(ROOT)}", "36")
    say(f"حجم محتوا: {len(preview)} کاراکتر", "90")
    if not confirm("این عملیات فایل را ایجاد یا جایگزین می‌کند."):
        return {"ok": False, "cancelled": True, "message": "کاربر عملیات را لغو کرد."}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_name(target.name + ".bak")
            shutil.copy2(target, backup)
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(preview, encoding="utf-8")
        temp.replace(target)
        backup_path = target.with_name(target.name + ".bak")
        return {
            "ok": True,
            "path": str(target.relative_to(ROOT)),
            "backup": str(backup_path.relative_to(ROOT)) if backup_path.exists() else None
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_command(command):
    command = str(command).strip()
    if not command:
        return {"ok": False, "error": "دستور خالی است."}
    say("دستور درخواستی:", "36")
    say(command, "97")
    say("توجه: دستورهای shell ممکن است به فایل‌های خارج از پوشه پروژه یا تنظیمات گوشی دسترسی داشته باشند.", "31")
    if not confirm("فقط در صورت اعتماد کامل دستور را اجرا کن."):
        return {"ok": False, "cancelled": True, "message": "کاربر اجرای دستور را لغو کرد."}
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
        output = result.stdout or "(بدون خروجی)"
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "output": output[-18000:]
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "زمان اجرای دستور از ۱۸۰ ثانیه بیشتر شد."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def execute_tool(name, args):
    try:
        if name == "list_files":
            return list_files(args.get("path", "."))
        if name == "read_file":
            return read_file(args["path"])
        if name == "write_file":
            return write_file(args["path"], args["content"])
        if name == "run_command":
            return run_command(args["command"])
        return {"ok": False, "error": "ابزار ناشناخته است."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    try:
        HISTORY_FILE.write_text(
            json.dumps(history[-MAX_HISTORY_ITEMS:], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as exc:
        say(f"ذخیره تاریخچه ناموفق بود: {exc}", "33")


def api_request(contents):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "tools": [{"functionDeclarations": FUNCTIONS}],
        "toolConfig": {
            "functionCallingConfig": {"mode": "AUTO"}
        },
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 8192
        }
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"خطای API ({exc.code}): {detail[:2500]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"خطای ارتباط اینترنت: {exc}")
    except TimeoutError:
        raise RuntimeError("زمان اتصال به API تمام شد.")


def extract_text(parts):
    texts = []
    for part in parts:
        if isinstance(part, dict) and "text" in part:
            texts.append(part["text"])
    return "\n".join(texts).strip()


def ask_gemini(history, user_text):
    history.append({"role": "user", "parts": [{"text": user_text}]})
    for _ in range(10):
        response = api_request(history)
        candidates = response.get("candidates", [])
        if not candidates:
            raise RuntimeError("پاسخی از مدل دریافت نشد: " + json.dumps(response, ensure_ascii=False)[:1500])
        candidate = candidates[0].get("content", {})
        parts = candidate.get("parts", [])
        history.append(candidate)

        calls = [
            part["functionCall"]
            for part in parts
            if isinstance(part, dict) and "functionCall" in part
        ]
        if not calls:
            answer = extract_text(parts)
            save_history(history)
            return answer or "مدل پاسخ متنی برنگرداند."

        function_responses = []
        for call in calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            say(f"در حال استفاده از ابزار: {name}", "90")
            result = execute_tool(name, args)
            function_responses.append({
                "functionResponse": {
                    "name": name,
                    "response": {"result": result}
                }
            })
        history.append({"role": "user", "parts": function_responses})

    save_history(history)
    raise RuntimeError("تعداد مراحل اجرای ابزارها بیش از حد مجاز شد.")


def show_help():
    say("راهنمای MSGN AI", "1;36")
    say("/help     نمایش راهنما")
    say("/files    نمایش فایل‌های پوشه کاری")
    say("/pwd      نمایش مسیر کاری")
    say("/clear    پاک کردن تاریخچه گفتگو")
    say("/model    نمایش مدل فعال")
    say("/exit     خروج")
    say("ویرایش ورودی: کلیدهای جهت‌دار، Home، End، Backspace و Delete")
    say("نمونه: فایل‌های پروژه را بررسی کن و خطاهای کد را پیدا کن.")
    print(line())


def main():
    if not API_KEY:
        say("کلید API پیدا نشد.", "31")
        say("ابتدا متغیر GEMINI_API_KEY را در محیط Termux تنظیم کن.", "33")
        say('نمونه امن برای وارد کردن موقت کلید: read -rsp "Gemini API Key: " GEMINI_API_KEY; export GEMINI_API_KEY; echo')
        return 1

    banner()
    history = load_history()
    say(f"تاریخچه قبلی: {len(history)} بخش", "90")
    say("MSGN AI آماده است. درخواستت را بنویس.", "32")
    print()

    while True:
        try:
            prompt = paint("┌─ MSGN", "1;38;5;45") + paint(" ❯ ", "1;38;5;39")
            user_text = read_persian_input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            say("\nبرای خروج از /exit استفاده کن.", "90")
            continue

        if not user_text:
            continue
        command = user_text.lower()

        if command in ("/exit", "/quit", "exit"):
            say("خروج از MSGN AI؛ موفق باشی!", "36")
            break
        if command == "/help":
            show_help()
            continue
        if command == "/pwd":
            say(str(ROOT), "36")
            continue
        if command == "/model":
            say(f"مدل فعال: {MODEL}", "36")
            continue
        if command == "/files":
            result = list_files(".")
            for item in result.get("items", []):
                icon = "📁" if item["type"] == "directory" else "📄"
                say(f'{icon} {item["name"]}')
            continue
        if command == "/clear":
            if confirm("تاریخچه گفتگو پاک شود؟"):
                history = []
                save_history(history)
                say("تاریخچه پاک شد.", "32")
            continue

        started = time.time()
        say("در حال پردازش درخواست...", "90")
        try:
            answer = ask_gemini(history, user_text)
            print()
            say("╭─ پاسخ MSGN AI", "1;38;5;45")
            say(answer)
            say("╰" + "─" * 58, "38;5;39")
            say(f"زمان پاسخ: {time.time() - started:.1f} ثانیه", "90")
        except Exception as exc:
            say(f"خطا: {exc}", "31")
            say("تاریخچه گفتگو برای جلوگیری از خراب‌شدن ذخیره نشد.", "90")
        print()


if __name__ == "__main__":
    raise SystemExit(main())

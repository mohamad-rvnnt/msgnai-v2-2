import os
import json
from pathlib import Path
from datetime import datetime

def analyze_project(target_path="."):
    root = Path(target_path).resolve()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": "مسیر معتبر نیست یا پوشه وجود ندارد."}
    
    project_name = root.name
    files_list = []
    languages = set()
    frameworks = set()
    dependencies = []
    important_files = []
    entry_point = None
    potential_issues = []
    
    # فایل‌های مهم و کلیدی که باید بررسی شوند
    key_files_map = {
        "requirements.txt": "Python Dependencies",
        "package.json": "Node.js Dependencies",
        "pyproject.toml": "Python Project Config",
        "Dockerfile": "Docker Container",
        "docker-compose.yml": "Docker Compose",
        ".git": "Git Repository",
        "main.py": "Python Entrypoint",
        "app.py": "Python Entrypoint",
        "index.js": "Node Entrypoint",
        "README.md": "Documentation"
    }
    
    # پیمایش پوشه پروژه
    for item in root.rglob("*"):
        if any(part.startswith('.') for part in item.parts if part != '.'):
            # نادیده گرفتن پوشه‌های مخفی مثل .git یا __pycache__ (به جز بررسی وجود .git)
            if item.name != ".git":
                continue
                
        if item.is_file():
            rel_path = str(item.relative_to(root))
            files_list.append(rel_path)
            
            # شناسایی زبان‌ها از روی پسوند
            ext = item.suffix.lower()
            if ext == ".py":
                languages.add("Python")
            elif ext in (".js", ".ts"):
                languages.add("JavaScript/TypeScript")
            elif ext == ".json":
                languages.add("JSON")
            elif ext in (".md",):
                languages.add("Markdown")
            elif ext in (".html", ".css"):
                languages.add("HTML/CSS")
                
            # شناسایی فایل‌های مهم
            if item.name in key_files_map:
                important_files.append(rel_path)
                
            # بررسی محتوای برخی فایل‌های خاص
            if item.name == "requirements.txt":
                try:
                    content = item.read_text(encoding="utf-8", errors="ignore")
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            dependencies.append(line)
                except Exception:
                    pass
                    
            elif item.name == "package.json":
                try:
                    data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
                    deps = data.get("dependencies", {})
                    for dep in deps:
                        dependencies.append(f"{dep}@ {deps[dep]}")
                    frameworks.add("Node.js / npm")
                except Exception:
                    pass
                    
            # تشخیص نقطه ورود (Entrypoint)
            if item.name in ("main.py", "app.py", "index.js", "server.js"):
                entry_point = rel_path

    # تشخیص فریم‌ورک‌ها بر اساس وابستگی‌ها یا فایل‌ها
    deps_str = " ".join(dependencies).lower()
    if "flask" in deps_str:
        frameworks.add("Flask")
    if "fastapi" in deps_str:
        frameworks.add("FastAPI")
    if "django" in deps_str:
        frameworks.add("Django")
    if "telegram" in deps_str or "pyrogram" in deps_str or "aiogram" in deps_str:
        frameworks.add("Telegram Bot Framework")
        
    # بررسی مشکلات احتمالی
    if not important_files:
        potential_issues.append("هیچ فایل پیکربندی یا مستنداتی (مثل README یا requirements) یافت نشد.")
    if "Python" in languages and "requirements.txt" not in [Path(f).name for f in important_files]:
        potential_issues.append("پروژه پایتون است اما فایل requirements.txt ندارد.")
    if not entry_point:
        potential_issues.append("فایل نقطه ورود مشخصی (مثل main.py یا app.py) شناسایی نشد.")

    # ساخت گزارش فنی
    report = {
        "project_name": project_name,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "languages": list(languages),
        "frameworks": list(frameworks),
        "important_files": important_files,
        "entry_point": entry_point or "نامشخص",
        "dependencies": dependencies[:35], # محدود کردن تعداد نمایش
        "total_files": len(files_list),
        "potential_issues": potential_issues
    }
    
    # ذخیره گزارش در پوشه reports
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"report_{project_name}_{int(datetime.now().timestamp())}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    report["report_path"] = str(report_file)
    return {"ok": True, "report": report}

if __name__ == "__main__":
    res = analyze_project(".")
    print(json.dumps(res, ensure_ascii=False, indent=2))

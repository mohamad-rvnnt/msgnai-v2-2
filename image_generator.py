import os
import urllib.request
import json
from pathlib import Path
from datetime import datetime

def generate_image(prompt_text, telegram_bot=None, chat_id=None):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    image_model = os.environ.get("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002").strip()
    
    if not api_key:
        return {"ok": False, "error": "کلید API برای تولید تصویر یافت نشد (GEMINI_API_KEY تنظیم نشده است)."}
        
    generated_dir = Path.cwd() / "memory" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"gen_{int(datetime.now().timestamp())}.jpg"
    dest_path = generated_dir / filename
    
    # نکته: ساختار درخواست Imagen در Gemini API (Vertex / v1beta)
    # اگر مدل یا انپوینت خاصی مد نظر باشد، اینجا مدیریت می‌شود.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{image_model}:predict?key={api_key}"
    
    payload = {
        "instances": [
            {"prompt": prompt_text}
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1"
        }
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            # بررسی ساختار پاسخ Imagen
            predictions = res_data.get("predictions", [])
            if not predictions:
                return {"ok": False, "error": "تصویری توسط مدل بازگردانده نشد."}
                
            # فرض بر دریافت base64 یا آدرس تصویر در خروجی
            image_b64 = predictions[0].get("bytesBase64Encoded")
            if image_b64:
                import base64
                image_bytes = base64.b64decode(image_b64)
                dest_path.write_bytes(image_bytes)
            else:
                return {"ok": False, "error": "فرمت پاسخ مدل تصویر نامعتبر است."}
                
        # ارسال خودکار به تلگرام در صورت وجود ربات و چت آیدی
        if telegram_bot and chat_id:
            # ارسال عکس از طریق Telegram Bot API (sendPhoto)
            try:
                # کد ارسال عکس با multipart/form-data یا متد ارسال تلگرام
                pass
            except Exception as e:
                print(f"Failed to send generated image to telegram: {e}")
                
        return {"ok": True, "path": str(dest_path), "filename": filename}
        
    except Exception as e:
        return {"ok": False, "error": f"خطا در تولید تصویر: {str(e)}"}

if __name__ == "__main__":
    print("Image Generator module loaded.")

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Đọc API Key từ .env hoặc dùng key mặc định
api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key and os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("GEMINI_API_KEY="):
                api_key = line.strip().split("=", 1)[1].strip()

import google.generativeai as genai
genai.configure(api_key=api_key)

print(f"[*] Đang kiểm tra API Key: {api_key[:8]}...{api_key[-4:]}", flush=True)

models_to_test = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]

for test_model in models_to_test:
    try:
        print(f"\n[+] Đang thử sinh nội dung với model: {test_model} ...", flush=True)
        model = genai.GenerativeModel(test_model)
        res = model.generate_content("Xin chào, bạn là ai? Hãy trả lời ngắn gọn trong 1 câu tiếng Việt.")
        print(f"[✓] THÀNH CÔNG với {test_model}!")
        print(f"    Phản hồi: {res.text.strip()}", flush=True)
        break
    except Exception as e:
        print(f"[!] Model {test_model} gặp lỗi: {e}", flush=True)

import json
import re
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from curl_cffi import requests


url = "https://www.tiktok.com/@swatchesbybaobao/live"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}
r = requests.get(url, headers=headers, impersonate="chrome120")
html = r.text

print(f"HTML length: {len(html)}")

# Tìm các thẻ script JSON
pattern = r'<script\s+id="([^"]+)"[^>]*>(.*?)</script>'
for script_id, content in re.findall(pattern, html, re.DOTALL):
    if script_id == "SIGI_STATE":
        print(f"\n[FOUND] Script ID: {script_id}")
        data = json.loads(content)
        live_room = data.get("LiveRoom", {})
        live_user_info = live_room.get("liveRoomUserInfo", {})
        print("LiveRoomUserInfo keys:", list(live_user_info.keys()))
        for k in live_user_info:
            print(f"  -> {k}: {str(live_user_info[k])[:300]}")




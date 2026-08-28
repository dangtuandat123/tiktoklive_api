import asyncio
from collections import Counter
import os
import sys


# Luôn ưu tiên import mã nguồn local
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live import TikTokLiveClient, EventType, get_ttwid


method_counter = Counter()
raw_methods = Counter()

async def sniff():
    username = "swatchesbybaobao"
    client = TikTokLiveClient(username)
    client.cookies(f"ttwid={get_ttwid(username)}")

    @client.on("*")
    def on_all(evt):
        method_counter[evt.type] += 1
        if evt.type == "unknown":
            m = evt.data.get("method")
            raw_methods[m] += 1
            payload = evt.data.get("payload", b"")
            print(f"[🔍 RAW UNKNOWN METHOD]: {m} | Size: {len(payload)} bytes", flush=True)
            # Thử giải mã nếu payload chứa text ASCII/UTF-8
            try:
                txt = payload.decode("utf-8", errors="ignore")
                printable = "".join(ch for ch in txt if ch.isprintable() or ch in " \n\t")
                if printable.strip():
                    print(f"    -> Payload string excerpt: {printable[:150]}", flush=True)
            except Exception:
                pass
        elif any(k in evt.type.lower() for k in ("shop", "oec", "pin", "ecom", "banner", "cart", "product", "order")):
            print(f"[🛍️ SHOPPING/PIN EVENT]: {evt.type} -> {evt.data}", flush=True)
        elif evt.type in ("chat", "gift", "like", "member", "join", "room_user_seq"):
            pass
        else:
            print(f"[⚡ EVENT]: {evt.type}", flush=True)

    print(f"[*] Bắt đầu bắt toàn bộ các gói tin Webcast từ @{username} trong 20 giây...", flush=True)
    try:
        await asyncio.wait_for(client.connect(), timeout=20)
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[!] Dừng bắt: {e}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("[*] THỐNG KÊ TẤT CẢ SỰ KIỆN ĐÃ BẮT ĐƯỢC:", flush=True)
    for k, v in method_counter.most_common():
        print(f"  - {k}: {v} gói tin", flush=True)

    if raw_methods:
        print("\n[*] CÁC METHOD UNKNOWN CHƯA CÓ TRONG ROUTER:", flush=True)
        for k, v in raw_methods.most_common():
            print(f"  - {k}: {v} lần xuất hiện", flush=True)

if __name__ == "__main__":
    asyncio.run(sniff())

#!/usr/bin/env python3
"""Ví dụ kết nối vào TikTok Live WebSocket Gateway Server bằng Python (ws_client_example.py).

Minh họa cách một backend khác (Node.js, C#, PHP, Python, Go) kết nối qua WebSocket
để nhận sự kiện trực tiếp từ ws_server.py.
"""

import asyncio
import json
import sys

# Đảm bảo UTF-8 trên Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import websockets


async def run_client():
    username = "swatchesbybaobao"
    server_uri = f"ws://localhost:8765/live?username={username}"

    print("=" * 80)
    print(f"🔌 ĐANG KẾT NỐI TỚI WEBSOCKET GATEWAY SERVER: {server_uri}")
    print("=" * 80)

    try:
        async with websockets.connect(server_uri) as ws:
            print("[+] Đã kết nối thành công! Đang chờ sự kiện từ phòng Live...\n")

            async for message in ws:
                data = json.loads(message)
                event_type = data.get("event")
                room = data.get("username")
                payload = data.get("data", {})

                if event_type == "subscribed":
                    print(f"✅ [ĐÃ ĐĂNG KÝ PHÒNG] @{room} | Trạng thái: {data.get('status')}")

                elif event_type == "chat":
                    u = payload.get("user", {})
                    nick = u.get("nickname") or "Ẩn danh"
                    comment = payload.get("comment", "")
                    fan_club = u.get("fan_club", {}).get("name", "")
                    badge_str = f"[{fan_club}] " if fan_club else ""
                    print(f"💬 [CHAT] {badge_str}{nick}: {comment}")

                elif event_type == "gift":
                    u = payload.get("user", {})
                    nick = u.get("nickname") or "Ẩn danh"
                    gift = payload.get("gift", {})
                    combo = payload.get("combo", {})
                    g_name = gift.get("name") or "Quà"
                    count = combo.get("event_gift_count", 1)
                    total = combo.get("total_gift_count", 1)
                    diamonds = combo.get("total_diamond_count", 0)
                    print(f"🎁 [GIFT] {nick} tặng +{count} {g_name} (Combo: x{total} | Tổng xu: {diamonds} 💎)")

                elif event_type == "like":
                    u = payload.get("user", {})
                    nick = u.get("nickname") or "Khán giả"
                    cnt = payload.get("event_like_count", 1)
                    total = payload.get("total_like_count", 0)
                    print(f"❤️ [LIKE] {nick} đã thả +{cnt} tim (Tổng tim: {total:,})")

                elif event_type == "oec_live_shopping":
                    p_title = payload.get("product_title", "")
                    p_id = payload.get("product_id", "")
                    p_url = payload.get("product_url", "")
                    seller = payload.get("seller", "")
                    sold = payload.get("sold_count", "")
                    action = payload.get("action_name", "")
                    print("\n" + "🛍️ " * 20)
                    print(f"🛍️ [TIKTOK SHOP] {action}")
                    if p_title:
                        print(f"   📦 Tên: {p_title}")
                    if p_id:
                        print(f"   🆔 ID: {p_id}")
                    if seller:
                        print(f"   🏪 Shop: {seller} | Lượt bán: {sold}")
                    if p_url:
                        print(f"   🔗 Link: {p_url}")
                    print("🛍️ " * 20 + "\n")

                elif event_type == "caption":
                    print(f"🎙️ [PHỤ ĐỀ AI]: {payload.get('content')}")

                elif event_type == "room_user_seq":
                    viewers = payload.get("viewer_count", 0)
                    total = payload.get("total_users", 0)
                    print(f"📊 [THỐNG KÊ] Đang xem: {viewers:,} người | Lượt ghé: {total:,}")

                else:
                    print(f"ℹ️ [{event_type.upper()}] {payload}")

    except Exception as e:
        print(f"[-] Lỗi kết nối WebSocket: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        print("\n[🛑 STOPPED] Đã dừng client.")

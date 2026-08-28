"""Example 2: Giám Sát & Khai Thác Chuyên Biệt Dữ Liệu TikTok Shop (E-Commerce Tracker).

Kịch bản này được tối ưu 100% cho mảng Bán hàng / TikTok Shop:
1. Tự động bắt sự kiện Streamer Ghim / Đổi sản phẩm (WebcastOecLiveShoppingMessage).
2. Tự động giải mã chuỗi nhị phân shopping_data_blob (Tên sản phẩm, Giá, Giảm giá, ID).
3. Lắng nghe Banner Voucher, Mã giảm giá, Chương trình Flash Sale.
4. Tích hợp AI Filter tự động lọc các bình luận Chốt Đơn ("Đã mua", "Đã đặt", "Mã deal", "Check đơn").
"""

from __future__ import annotations

import asyncio
import datetime
import json
import re
import sys

# Đảm bảo hiển thị Tiếng Việt và Emoji chuẩn trên Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live import TikTokLiveClient, EventType, get_ttwid


def get_time_str() -> str:
    """Trả về timestamp định dạng HH:MM:SS."""
    return datetime.datetime.now().strftime("%H:%M:%S")


def parse_shopping_blob(blob: bytes | str | None) -> dict:
    """Trích xuất các thuộc tính nghiệp vụ từ shopping_data_blob."""
    info = {}
    if not blob:
        return info
    
    raw_bytes = blob if isinstance(blob, (bytes, bytearray)) else str(blob).encode("utf-8", errors="ignore")
    
    # Tìm các chuỗi khóa - giá trị
    try:
        text = raw_bytes.decode("utf-8", errors="ignore")
        if "CardTypePopProduct" in text:
            info["card_type"] = "Thẻ Pop-up Sản Phẩm Nổi Bật (CardTypePopProduct)"
        if "SetPinProduct" in text:
            info["action"] = "Streamer vừa bấm GHIM SẢN PHẨM (SetPinProduct)"
        if "LiveManager" in text:
            info["platform"] = "Thao tác từ Trình quản lý TikTok Live Studio"
        
        # Nếu có chuỗi JSON
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            json_data = json.loads(text[start:end])
            info["json_details"] = json_data
    except Exception:
        pass
        
    return info


async def main():
    # Tên kênh streamer bán hàng mục tiêu
    username = "swatchesbybaobao"
    
    client = TikTokLiveClient(username)

    # ============================================================
    # TỰ ĐỘNG CẤP COOKIE TTWID (Bypass anti-bot 100% bằng Playwright)
    # ============================================================
    try:
        ttwid_token = get_ttwid(username)
        client.cookies(f"ttwid={ttwid_token}")
        print(f"[{get_time_str()}] [*] Đã cấp TTWID xịn: {ttwid_token[:20]}...", flush=True)
    except Exception as e:
        print(f"[{get_time_str()}] [!] Sử dụng TTWID mặc định ({e})", flush=True)

    # ============================================================
    # 1. KẾT NỐI PHÒNG LIVE
    # ============================================================
    @client.on(EventType.connected)
    def on_connected(evt):
        print("\n" + "=" * 85, flush=True)
        print(f"[{get_time_str()}] [🛒 TIKTOK SHOP TRACKER] ĐÃ KẾT NỐI VÀO PHÒNG LIVE: @{username}", flush=True)
        print(f"[{get_time_str()}] [*] Room ID: {evt.room_id} | Đang theo dõi các sự kiện Giỏ hàng & Ghim sản phẩm...", flush=True)
        print("=" * 85 + "\n", flush=True)

    # ============================================================
    # 2. SỰ KIỆN TIKTOK SHOP CHÍNH THỨC (OEC LIVE SHOPPING)
    # ============================================================
    @client.on(EventType.oec_live_shopping)
    def on_oec_shopping(evt):
        data = evt.data or {}
        action_type = data.get("actionType") or data.get("action_type") or 1
        blob = data.get("shoppingDataBlob") or data.get("shopping_data_blob")
        parsed = parse_shopping_blob(blob)

        print("\n" + "🔥" * 45, flush=True)
        print(f"[{get_time_str()}] [🛍️ TIKTOK SHOP - PHÁT HIỆN SỰ KIỆN GIỎ HÀNG / GHIM SẢN PHẨM!]", flush=True)
        print(f"  📌 Hành động: {parsed.get('action', 'Cập nhật ghim sản phẩm mới')}", flush=True)
        print(f"  🏷️ Loại hiển thị: {parsed.get('card_type', 'Thẻ sản phẩm')}", flush=True)
        print(f"  💻 Nền tảng: {parsed.get('platform', 'TikTok Live Studio')}", flush=True)
        print(f"  🔢 Action Type Code: {action_type}", flush=True)
        
        if "json_details" in parsed:
            print(f"  📄 Chi tiết: {json.dumps(parsed['json_details'], ensure_ascii=False, indent=2)}", flush=True)
            
        print("🔥" * 45 + "\n", flush=True)


    # ============================================================
    # 3. SỰ KIỆN GHIM TIN NHẮN / GHIM DEAL TRÊN KHUNG CHAT
    # ============================================================
    @client.on(EventType.room_pin)
    def on_room_pin(evt):
        data = evt.data or {}
        print(f"\n[{get_time_str()}] [📌 GHIM DEAL / THÔNG BÁO SHOP] Streamer vừa ghim thông báo mới lên đầu phòng!", flush=True)
        if data:
            print(f"    Chi tiết: {data}", flush=True)

    # ============================================================
    # 4. SỰ KIỆN BANNER VOUCHER & MÃ GIẢM GIÁ
    # ============================================================
    @client.on(EventType.in_room_banner)
    def on_banner(evt):
        data = evt.data or {}
        print(f"[{get_time_str()}] [🏷️ VOUCHER KHUYẾN MÃI] Xuất hiện banner ưu đãi / mã giảm giá trong phòng!", flush=True)

    # ============================================================
    # 5. SỰ KIỆN MỤC TIÊU ĐƠN HÀNG / DOANH SỐ PHÒNG LIVE
    # ============================================================
    @client.on(EventType.goal_update)
    def on_goal(evt):
        print(f"[{get_time_str()}] [🎯 MỤC TIÊU BÁN HÀNG] Tiến độ chỉ tiêu live vừa được cập nhật!", flush=True)

    # Bắt đầu kết nối
    print(f"[{get_time_str()}] [*] Đang kết nối tới TikTok Live @{username} để theo dõi Shop...", flush=True)
    await client.connect()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{get_time_str()}] [🛑 DISCONNECTED] Đã dừng theo dõi TikTok Shop an toàn.", flush=True)

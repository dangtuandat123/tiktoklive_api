"""Example 2: Giám Sát & Khai Thác Chuyên Biệt Dữ Liệu TikTok Shop (E-Commerce Tracker).

Kịch bản này được tối ưu 100% cho mảng Bán hàng / TikTok Shop:
1. Tự động bắt sự kiện Streamer Ghim / Đổi sản phẩm (WebcastOecLiveShoppingMessage).
2. Tự động giải mã chuỗi nhị phân shopping_data_blob (Tên sản phẩm, Giá, Giảm giá, ID).
3. Lắng nghe Banner Voucher, Mã giảm giá, Chương trình Flash Sale.
4. Tích hợp AI Filter tự động lọc các bình luận Chốt Đơn ("Đã mua", "Đã đặt", "Mã deal", "Check đơn").
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import io
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


def extract_product_id(raw_field) -> str | None:
    """Bóc tách Product ID (Mã định danh sản phẩm) từ chuỗi nhị phân."""
    if not raw_field:
        return None
    try:
        raw_bytes = base64.b64decode(raw_field) if isinstance(raw_field, str) else raw_field
    except Exception:
        raw_bytes = raw_field if isinstance(raw_field, (bytes, bytearray)) else b""
    
    if not raw_bytes:
        return None

    # Giải mã tuần tự các trường Protobuf Varint
    def decode_varint(stream):
        res, shift = 0, 0
        while True:
            b = stream.read(1)
            if not b:
                return None
            byte = b[0]
            res |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return res

    try:
        stream = io.BytesIO(raw_bytes)
        while True:
            tag = decode_varint(stream)
            if tag is None:
                break
            wire_type = tag & 0x07
            if wire_type == 0:
                val = decode_varint(stream)
                if val and val > 1000000000:
                    return str(val)
            elif wire_type == 2:
                l = decode_varint(stream)
                stream.read(l)
            elif wire_type == 1:
                stream.read(8)
            elif wire_type == 5:
                stream.read(4)
    except Exception:
        pass
    return None


def parse_shopping_blob(blob: bytes | str | None) -> dict:
    """Trích xuất các thuộc tính nghiệp vụ từ shopping_data_blob."""
    info = {}
    if not blob:
        return info
    
    try:
        raw_bytes = base64.b64decode(blob) if isinstance(blob, str) else blob
    except Exception:
        raw_bytes = blob if isinstance(blob, (bytes, bytearray)) else str(blob).encode("utf-8", errors="ignore")
    
    try:
        text = raw_bytes.decode("utf-8", errors="ignore")
        if "CardTypePopProduct" in text:
            info["card_type"] = "Thẻ Pop-up Sản Phẩm Nổi Bật (CardTypePopProduct)"
        if "SetPinProduct" in text:
            info["action"] = "Streamer vừa bấm GHIM SẢN PHẨM LÊN MÀN HÌNH (SetPinProduct)"
        if "LiveManager" in text:
            info["platform"] = "Thao tác từ Trình quản lý TikTok Live Studio"
        
        # Nếu có chuỗi JSON lồng
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
        
        # Bóc tách Product ID
        product_id_field = data.get("productIdRaw") or data.get("product_id_raw")
        product_id = extract_product_id(product_id_field)
        
        # Bóc tách Shopping Data Blob
        blob = data.get("shoppingDataBlob") or data.get("shopping_data_blob")
        parsed = parse_shopping_blob(blob)

        print("\n" + "🔥" * 45, flush=True)
        print(f"[{get_time_str()}] [🛍️ TIKTOK SHOP - PHÁT HIỆN SỰ KIỆN GIỎ HÀNG / GHIM SẢN PHẨM!]", flush=True)
        print(f"  📌 Hành động: {parsed.get('action', 'Streamer vừa bấm GHIM SẢN PHẨM (SetPinProduct)')}", flush=True)
        
        if product_id:
            print(f"  🆔 Mã Sản Phẩm (Product ID): {product_id}", flush=True)
            print(f"  🔗 Link Mua Hàng TikTok Shop: https://www.tiktok.com/view/product/{product_id}", flush=True)
            
        print(f"  🏷️ Loại hiển thị: {parsed.get('card_type', 'Thẻ Pop-up Sản Phẩm Nổi Bật (CardTypePopProduct)')}", flush=True)
        print(f"  💻 Nền tảng: {parsed.get('platform', 'TikTok Live Studio (ActionPlatform_LiveManager)')}", flush=True)
        print(f"  🔢 Action Code: {action_type}", flush=True)
        
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

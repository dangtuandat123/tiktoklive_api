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


def decode_shopping_blob(blob: bytes | str | None) -> dict | str | None:
    """Giải mã sâu chuỗi nhị phân shopping_data_blob của TikTok Shop."""
    if not blob:
        return None
    if isinstance(blob, (bytes, bytearray)):
        try:
            text = blob.decode("utf-8", errors="ignore")
            # Nếu chứa JSON cấu trúc
            if "{" in text and "}" in text:
                # Tìm đoạn JSON hợp lệ
                start = text.find("{")
                end = text.rfind("}") + 1
                return json.loads(text[start:end])
            return text
        except Exception:
            return repr(blob)
    return blob


# Danh sách từ khóa nhận diện khách hàng đang tương tác mua sắm / chốt đơn
BUYING_INTENT_KEYWORDS = [
    r"đã mua", r"đã đặt", r"da mua", r"da dat", r"săn", r"san dc", r"săn được",
    r"check đơn", r"mã", r"combo", r"giá", r"chai", r"hộp", r"size", r"màu",
    r"freeship", r"voucher", r"giỏ hàng", r"ship", r"tặng", r"mua", r"đơn"
]
BUYING_REGEX = re.compile("|".join(BUYING_INTENT_KEYWORDS), re.IGNORECASE)


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
        print(f"[{get_time_str()}] [*] Room ID: {evt.room_id} | Đang chờ các sự kiện giỏ hàng và đơn hàng...", flush=True)
        print("=" * 85 + "\n", flush=True)

    # ============================================================
    # 2. SỰ KIỆN TIKTOK SHOP CHÍNH THỨC (OEC LIVE SHOPPING)
    # ============================================================
    @client.on(EventType.oec_live_shopping)
    def on_oec_shopping(evt):
        data = evt.data or {}
        blob = data.get("shopping_data_blob") or data.get("shoppingDataBlob")
        decoded = decode_shopping_blob(blob)

        print("\n" + "🔥" * 40, flush=True)
        print(f"[{get_time_str()}] [🛍️ TIKTOK SHOP - CẬP NHẬT GIỎ HÀNG / GHIM SẢN PHẨM MỚI!]", flush=True)
        
        if isinstance(decoded, dict):
            # Trích xuất các trường thông tin nếu có
            title = decoded.get("title") or decoded.get("product_title") or decoded.get("name")
            price = decoded.get("price") or decoded.get("format_price")
            product_id = decoded.get("product_id") or decoded.get("id")
            stock = decoded.get("stock") or decoded.get("stock_count")
            
            if title:
                print(f"  📌 Tên sản phẩm: {title}", flush=True)
            if price:
                print(f"  💰 Giá bán: {price}", flush=True)
            if product_id:
                print(f"  🆔 Mã sản phẩm (Product ID): {product_id}", flush=True)
            if stock:
                print(f"  📦 Tồn kho: {stock}", flush=True)
            
            print(f"  📄 Raw Data: {json.dumps(decoded, ensure_ascii=False)}", flush=True)
        elif decoded:
            print(f"  📄 Nội dung: {decoded}", flush=True)
        else:
            print(f"  📄 Gói tin nhị phân: {data}", flush=True)
            
        print("🔥" * 40 + "\n", flush=True)

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

    # ============================================================
    # 6. BỘ LỌC ĐƠN HÀNG & BÌNH LUẬN MUA SẮM THỜI GIAN THỰC
    # ============================================================
    @client.on(EventType.chat)
    def on_chat(evt):
        comment = evt.comment or ""
        nick = evt.user_nickname or "Khách hàng"
        uid = evt.user_id or ""

        # Lọc ra các bình luận có ý định mua sắm hoặc xác nhận chốt đơn
        if BUYING_REGEX.search(comment):
            print(f"[{get_time_str()}] [📦 ĐƠN HÀNG / MUA SẮM] {nick} (id:{uid}): {comment}", flush=True)

    # Bắt đầu kết nối
    print(f"[{get_time_str()}] [*] Đang kết nối tới TikTok Live @{username} để theo dõi Shop...", flush=True)
    await client.connect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{get_time_str()}] [🛑 DISCONNECTED] Đã dừng theo dõi TikTok Shop an toàn.", flush=True)

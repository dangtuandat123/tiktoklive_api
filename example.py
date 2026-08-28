import asyncio
import sys

# Đảm bảo in tiếng Việt & Emoji trên Windows không bị lỗi bảng mã
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live import TikTokLiveClient, EventType, get_ttwid


async def main():
    username = "swatchesbybaobao"
    client = TikTokLiveClient(username)

    # ============================================================
    # TỰ ĐỘNG LẤY TTWID BẰNG PLAYWRIGHT (Chuẩn 100% không bao giờ bị chặn)
    # Token được tự động cache trong .ttwid_cache.json để tái sử dụng tức thì
    # ============================================================
    try:
        ttwid_token = get_ttwid(username)
        client.cookies(f"ttwid={ttwid_token}")
        print(f"[*] Đã cấp TTWID: {ttwid_token[:20]}...")
    except Exception as e:
        print(f"[!] Không thể lấy TTWID qua Playwright ({e}), sẽ dùng curl_cffi mặc định.")


    # Tùy chọn: Đặt User-Agent trình duyệt thật
    client.user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Đăng ký nhận sự kiện Kết nối thành công
    @client.on(EventType.connected)
    def on_connected(evt):
        print(f"\n[🚀 Connected] Kết nối thành công tới phòng Live ID: {evt.room_id}", flush=True)

    # 1. Đăng ký nhận sự kiện Bình luận chữ (Chat)
    @client.on(EventType.chat)
    def on_chat(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or user.get("nickName") or "Ẩn danh"
        comment = data.get("content") or data.get("comment") or ""
        print(f"[💬 Chat] {nick}: {comment}", flush=True)

    # 2. Đăng ký nhận sự kiện Emote / Sticker Chat
    @client.on(EventType.emote_chat)
    def on_emote(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        print(f"[😀 Emote] {nick} đã gửi sticker/emote!", flush=True)

    # 3. Đăng ký nhận sự kiện Tin nhắn phòng / Host / Hệ thống
    @client.on(EventType.room_message)
    def on_room_msg(evt):
        data = evt.data or {}
        content = data.get("content") or ""
        print(f"[📢 Phòng/Host] {content}", flush=True)

    # 4. Đăng ký nhận sự kiện Tặng Quà (Gift)
    @client.on(EventType.gift)
    def on_gift(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        gift = data.get("gift") or {}
        gift_name = gift.get("name") or "Quà"
        count = data.get("repeat_count") or data.get("repeatCount") or 1
        diamonds = evt.data.get("diamond_total") or gift.get("diamondCount", 0)
        print(f"[🎁 Gift] {nick} tặng {gift_name} x{count} ({diamonds} xu)", flush=True)


    # Đăng ký nhận sự kiện Thả Tim (Like)
    @client.on(EventType.like)
    def on_like(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        total = data.get("total") or 0
        count = data.get("count") or 1
        print(f"[❤️ Like] {nick} đã thả +{count} tim (Tổng: {total})", flush=True)

    # Đăng ký nhận sự kiện Ghim Giỏ hàng / TikTok Shop
    @client.on(EventType.oec_live_shopping)
    def on_shopping(evt):
        print(f"[🛍️ TikTok Shop] Có sự kiện giỏ hàng mới: {evt.data}", flush=True)

    print(f"[*] Đang kết nối tới phòng live @{username}...", flush=True)
    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())
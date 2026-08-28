import asyncio
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

    # Đăng ký nhận sự kiện Bình luận (Chat)
    @client.on(EventType.chat)
    def on_chat(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or user.get("nickName") or "Ẩn danh"
        comment = data.get("content") or data.get("comment") or ""
        print(f"[💬 Chat] {nick}: {comment}")

    # Đăng ký nhận sự kiện Tặng Quà (Gift)
    @client.on(EventType.gift)
    def on_gift(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        gift = data.get("gift") or {}
        gift_name = gift.get("name") or "Quà"
        count = data.get("repeatCount") or 1
        diamonds = gift.get("diamondCount", 0)
        print(f"[🎁 Gift] {nick} tặng {gift_name} x{count} ({diamonds} xu)")

    # Đăng ký nhận sự kiện Thả Tim (Like)
    @client.on(EventType.like)
    def on_like(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        total = data.get("total") or 0
        print(f"[❤️ Like] {nick} đã thả tim (Tổng: {total})")

    # Đăng ký nhận sự kiện Ghim Giỏ hàng / TikTok Shop
    @client.on(EventType.oec_live_shopping)
    def on_shopping(evt):
        print(f"[🛍️ TikTok Shop] Có sự kiện giỏ hàng mới!")

    print("Đang kết nối tới phòng live...")
    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())
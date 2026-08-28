import asyncio
import datetime
import sys

# Đảm bảo in tiếng Việt & Emoji trên Windows không bị lỗi bảng mã
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live import (
    TikTokLiveClient,
    EventType,
    GiftStreakTracker,
    LikeAccumulator,
    get_ttwid,
)


def get_time_str() -> str:
    """Trả về timestamp hiện tại dạng HH:MM:SS."""
    return datetime.datetime.now().strftime("%H:%M:%S")


def format_user_badge(data: dict) -> str:
    """Trích xuất danh xưng / huy hiệu của người dùng (Host, Mod, Sub, Fan)."""
    user = data.get("user") or {}
    user_identity = data.get("user_identity") or {}
    fans_club = user.get("fans_club") or {}
    fans_data = fans_club.get("data") or {}

    badges = []
    if user_identity.get("is_anchor"):
        badges.append("👑 HOST")
    elif user_identity.get("is_moderator_of_anchor") or user.get("user_attr", {}).get("is_admin"):
        badges.append("🛡️ MOD")
    if user_identity.get("is_subscriber_of_anchor"):
        badges.append("⭐ SUB")
    if fans_data.get("club_name"):
        club_name = fans_data.get("club_name")
        level = fans_data.get("level", 1)
        badges.append(f"🎖️ {club_name} Lv.{level}")

    badge_str = f"[{' | '.join(badges)}] " if badges else ""
    return badge_str


async def main():
    username = "swatchesbybaobao"
    client = (
        TikTokLiveClient(username)
        # Prefetch 20 bình luận lịch sử ngay khi vừa vào phòng
        .history_comment_count(20)
    )

    # Khởi tạo các helper tính toán dữ liệu chuẩn xác
    streak_tracker = GiftStreakTracker()
    like_acc = LikeAccumulator()

    # ============================================================
    # TỰ ĐỘNG CẤP COOKIE TTWID (Bypass anti-bot 100% bằng Playwright)
    # ============================================================
    try:
        ttwid_token = get_ttwid(username)
        client.cookies(f"ttwid={ttwid_token}")
        print(f"[{get_time_str()}] [*] Đã cấp TTWID thành công: {ttwid_token[:20]}...", flush=True)
    except Exception as e:
        print(f"[{get_time_str()}] [!] Lỗi Playwright ({e}), sẽ dùng curl_cffi mặc định.", flush=True)

    # ============================================================
    # 1. SỰ KIỆN KẾT NỐI & ĐIỀU KHIỂN PHÒNG
    # ============================================================
    @client.on(EventType.connected)
    def on_connected(evt):
        print(f"\n[{get_time_str()}] [🚀 CONNECTED] Kết nối thành công tới phòng Live ID: {evt.room_id}", flush=True)
        print("=" * 80, flush=True)

    @client.on(EventType.disconnected)
    def on_disconnected(evt):
        print(f"\n[{get_time_str()}] [🔌 DISCONNECTED] Đã ngắt kết nối khỏi phòng Live.", flush=True)

    @client.on(EventType.reconnecting)
    def on_reconnecting(evt):
        data = evt.data or {}
        print(f"[{get_time_str()}] [🔄 RECONNECTING] Đang kết nối lại lần {data.get('attempt')}/{data.get('max_retries')} (chờ {data.get('delay')}s)...", flush=True)

    @client.on(EventType.live_ended)
    def on_live_ended(evt):
        print(f"\n[{get_time_str()}] [🛑 LIVE ENDED] Streamer đã tắt buổi phát trực tiếp!", flush=True)

    # ============================================================
    # 2. SỰ KIỆN BÌNH LUẬN & TIN NHẮN (CHAT / EMOTE / ROOM MESSAGE)
    # ============================================================
    @client.on(EventType.chat)
    def on_chat(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or user.get("unique_id") or "Ẩn danh"
        uid = user.get("id") or ""
        comment = data.get("content") or data.get("comment") or ""
        badge = format_user_badge(data)
        
        print(f"[{get_time_str()}] [💬 CHAT] {badge}{nick} (id:{uid}): {comment}", flush=True)

    @client.on(EventType.emote_chat)
    def on_emote(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        badge = format_user_badge(data)
        print(f"[{get_time_str()}] [😀 EMOTE] {badge}{nick} đã gửi sticker cảm xúc", flush=True)

    @client.on(EventType.room_message)
    def on_room_msg(evt):
        data = evt.data or {}
        content = data.get("content") or ""
        print(f"[{get_time_str()}] [📢 THÔNG BÁO PHÒNG] {content}", flush=True)

    @client.on(EventType.room_pin)
    def on_room_pin(evt):
        print(f"[{get_time_str()}] [📌 GHIM TIN NHẮN] Có tin nhắn vừa được ghim lên đầu phòng live!", flush=True)

    # ============================================================
    # 3. SỰ KIỆN TẶNG QUÀ (GIFT & COMBO STREAK TRACKING)
    # ============================================================
    @client.on(EventType.gift)
    def on_gift(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        gift = data.get("gift") or {}
        gift_name = gift.get("name") or "Quà"
        diamond_unit = gift.get("diamond_count") or 0
        badge = format_user_badge(data)

        # Xử lý tính toán chuỗi combo quà tặng chính xác qua helper
        streak = streak_tracker.process(data)
        if streak.is_active:
            status = f"🔥 COMBO STREAK: x{streak.total_gift_count} (+{streak.event_gift_count} mới)"
        else:
            status = f"🎁 ĐÃ TẶNG: x{streak.total_gift_count}"

        print(
            f"[{get_time_str()}] [🎁 GIFT] {badge}{nick} -> {gift_name} | {status} "
            f"| +{streak.event_diamond_count} xu (Tổng: {streak.total_diamond_count} xu / {diamond_unit} xu mỗi quà)",
            flush=True,
        )

    # ============================================================
    # 4. SỰ KIỆN THẢ TIM (LIKE & MONOTONIC ACCUMULATOR)
    # ============================================================
    @client.on(EventType.like)
    def on_like(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        
        # Ổn định hóa số like không bị nhảy lùi giữa các server shard
        stats = like_acc.process(data)
        print(
            f"[{get_time_str()}] [❤️ LIKE] {nick} đã thả +{stats.event_like_count} tim "
            f"(Tổng tim toàn phòng: {stats.total_like_count:,})",
            flush=True,
        )

    # ============================================================
    # 5. SỰ KIỆN TƯƠNG TÁC (VÀO PHÒNG / FOLLOW / SHARE)
    # ============================================================
    @client.on(EventType.join)
    def on_join(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        total_member = data.get("member_count") or 0
        badge = format_user_badge(data)
        print(f"[{get_time_str()}] [🚪 VÀO PHÒNG] {badge}{nick} vừa vào xem (Số người xem: {total_member:,})", flush=True)

    @client.on(EventType.follow)
    def on_follow(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        print(f"[{get_time_str()}] [➕ FOLLOW] {nick} đã bấm THEO DÕI streamer!", flush=True)

    @client.on(EventType.share)
    def on_share(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        share_target = data.get("share_target") or "bạn bè"
        print(f"[{get_time_str()}] [🔗 SHARE] {nick} đã CHIA SẺ livestream tới {share_target}!", flush=True)

    # ============================================================
    # 6. SỰ KIỆN THỐNG KÊ NGƯỜI XEM & TOP BXH (ROOM USER SEQ)
    # ============================================================
    @client.on(EventType.room_user_seq)
    def on_user_seq(evt):
        data = evt.data or {}
        viewers = data.get("viewer_count") or 0
        total_user = data.get("total_user") or 0
        ranks = data.get("ranks_list") or []
        top1 = ""
        if ranks and len(ranks) > 0:
            top_user = ranks[0].get("user") or {}
            top_nick = top_user.get("nickname") or "Ẩn danh"
            top_score = ranks[0].get("score") or 0
            top1 = f" | 🥇 Top 1 BXH: {top_nick} ({top_score:,} điểm)"

        print(f"[{get_time_str()}] [📊 THỐNG KÊ] Đang xem: {viewers:,} người | Tổng lượt ghé: {total_user:,}{top1}", flush=True)

    # ============================================================
    # 7. SỰ KIỆN TIKTOK SHOP / THƯƠNG MẠI ĐIỆN TỬ
    # ============================================================
    @client.on(EventType.oec_live_shopping)
    def on_shopping(evt):
        data = evt.data or {}
        print(f"[{get_time_str()}] [🛍️ TIKTOK SHOP] Có sự kiện giỏ hàng / ghim sản phẩm mới!", flush=True)

    # ============================================================
    # 8. SỰ KIỆN PK BATTLE / LINK MIC & HỘI VIÊN
    # ============================================================
    @client.on(EventType.link_mic_battle)
    def on_pk(evt):
        data = evt.data or {}
        print(f"[{get_time_str()}] [⚔️ PK BATTLE] Trận đấu PK cập nhật (Battle ID: {data.get('battle_id')})", flush=True)

    @client.on(EventType.question_new)
    def on_question(evt):
        data = evt.data or {}
        details = data.get("details") or {}
        q_text = details.get("question_text") or ""
        user = details.get("user") or {}
        nick = user.get("nickname") or "Ẩn danh"
        print(f"[{get_time_str()}] [❓ HỎI ĐÁP Q&A] {nick} hỏi: {q_text}", flush=True)

    @client.on(EventType.sub_notify)
    def on_sub(evt):
        data = evt.data or {}
        user = data.get("user") or {}
        nick = user.get("nickname") or "Khán giả"
        month = data.get("sub_month") or 1
        print(f"[{get_time_str()}] [⭐ HỘI VIÊN] {nick} đã đăng ký hội viên tháng thứ {month}!", flush=True)

    @client.on(EventType.envelope)
    def on_envelope(evt):
        data = evt.data or {}
        info = data.get("envelope_info") or {}
        sender = info.get("send_user_name") or "Ai đó"
        diamonds = info.get("diamond_count") or 0
        print(f"[{get_time_str()}] [🧧 BAO LÌ XÌ] {sender} đã thả bao lì xì trị giá {diamonds:,} kim cương!", flush=True)

    # Bắt đầu kết nối
    print(f"[{get_time_str()}] [*] Đang kết nối tới phòng live @{username}...", flush=True)
    await client.connect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{get_time_str()}] [🛑 DISCONNECTED] Đã ngắt kết nối an toàn theo yêu cầu người dùng.", flush=True)
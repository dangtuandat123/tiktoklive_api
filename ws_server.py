#!/usr/bin/env python3
"""TikTok Live WebSocket Gateway Server (ws_server.py).

Cho phép các hệ thống bên ngoài (Node.js, C#, PHP, Java, Go, OBS Browser Source,
Web Frontend, Unity Game Engine) kết nối qua giao thức WebSocket chuẩn để nhận
toàn bộ 100% sự kiện TikTok Live thời gian thực dưới định dạng JSON chuẩn hóa.

Cách kết nối:
    1. Query Param (Cực tiện cho Web/OBS/Unity):
       ws://localhost:8765/live?username=swatchesbybaobao

    2. JSON Command (Cho Microservices / Backend):
       ws://localhost:8765
       -> Gửi: {"action": "subscribe", "username": "swatchesbybaobao"}
       -> Gửi: {"action": "unsubscribe", "username": "swatchesbybaobao"}
       -> Gửi: {"action": "list_rooms"}
       -> Gửi: {"action": "get_room_status", "username": "swatchesbybaobao"}
       -> Gửi: {"action": "stats"}
       -> Gửi: {"action": "ping"}

Cách chạy server:
    python ws_server.py                     # Chạy mặc định trên 0.0.0.0:8765
    python ws_server.py --port 9000        # Đổi cổng sang 9000
    python ws_server.py --proxy "http://127.0.0.1:8080"
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set

# Đảm bảo UTF-8 trên Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import websockets
from websockets.asyncio.server import ServerConnection, serve

from piratetok_live import (
    EventType,
    GiftStreakTracker,
    LikeAccumulator,
    ProductInfo,
    TikTokEvent,
    TikTokLiveClient,
    get_ttwid,
)
from piratetok_live.errors import (
    AgeRestrictedError,
    DeviceBlockedError,
    HostNotOnlineError,
    TikTokApiError,
    TikTokBlockedError,
    UserNotFoundError,
)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger("ws_gateway")


def get_iso_time() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def serialize_user(evt: TikTokEvent) -> Dict[str, Any]:
    """Chuẩn hóa thông tin người dùng gửi sự kiện kèm huy hiệu."""
    u = evt.user
    thumb = u.get("avatar_thumb") or u.get("avatarThumb") or {}
    urls = thumb.get("url_list") or thumb.get("urlList") or []
    avatar_url = str(urls[0]) if urls else ""

    return {
        "id": evt.user_id,
        "nickname": evt.user_nickname,
        "unique_id": evt.user_unique_id,
        "sec_uid": evt.sec_uid,
        "avatar_url": avatar_url,
        "is_host": evt.is_host,
        "is_mod": evt.is_mod,
        "is_sub": evt.is_sub,
        "is_fan": evt.is_fan,
        "fan_club": {
            "name": evt.fans_club_name,
            "level": evt.fans_club_level,
        },
    }


class RoomHub:
    """Quản lý 1 phòng Live duy nhất trên TikTok và phát sóng tới các client bên ngoài."""

    def __init__(self, username: str, proxy: str = "", idle_timeout: float = 30.0):
        self.username = username.strip().lstrip("@").lower()
        self.proxy = proxy
        self.idle_timeout = idle_timeout

        self.clients: Set[ServerConnection] = set()
        self.client_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        self.room_id: str = ""
        self.is_connected = False

        # Các helper tính toán dữ liệu
        self.streak_tracker = GiftStreakTracker()
        self.like_acc = LikeAccumulator()
        self.active_product_id: str = ""
        self.active_product_info: Optional[ProductInfo] = None

        self.total_broadcasts = 0
        self.last_empty_time: Optional[float] = None
        self.created_at = time.time()

    def add_client(self, ws: ServerConnection):
        self.clients.add(ws)
        self.last_empty_time = None
        _log.info(f"➕ [Room @{self.username}] Client kết nối mới. Tổng clients: {len(self.clients)}")

    def remove_client(self, ws: ServerConnection):
        self.clients.discard(ws)
        _log.info(f"➖ [Room @{self.username}] Client đã ngắt. Còn lại: {len(self.clients)} clients")
        if len(self.clients) == 0:
            self.last_empty_time = time.time()

    def should_cleanup(self) -> bool:
        if len(self.clients) == 0 and self.last_empty_time is not None:
            return (time.time() - self.last_empty_time) >= self.idle_timeout
        return False

    async def broadcast(self, payload: Dict[str, Any]):
        """Gửi gói tin JSON tới toàn bộ client đang theo dõi phòng này."""
        if not self.clients:
            return
        self.total_broadcasts += 1
        message_str = json.dumps(payload, ensure_ascii=False)
        stale_clients = []
        for ws in list(self.clients):
            try:
                await ws.send(message_str)
            except Exception:
                stale_clients.append(ws)

        for ws in stale_clients:
            self.remove_client(ws)

    def start_worker(self, ttwid_token: str):
        """Khởi động worker kết nối ngầm tới TikTok Live."""
        if self.client_task is None or self.client_task.done():
            self.stop_event.clear()
            self.client_task = asyncio.create_task(self._run_tiktok_client(ttwid_token))

    async def stop(self):
        """Dừng kết nối TikTok Live của phòng này."""
        self.stop_event.set()
        if self.client_task and not self.client_task.done():
            self.client_task.cancel()
            try:
                await self.client_task
            except asyncio.CancelledError:
                pass
        _log.info(f"🛑 [Room @{self.username}] Đã dừng worker TikTok Live.")

    async def _run_tiktok_client(self, ttwid_token: str):
        _log.info(f"🚀 [Room @{self.username}] Đang khởi động TikTokLiveClient...")
        client = (
            TikTokLiveClient(self.username)
            .cookies(f"ttwid={ttwid_token}")
            .max_retries(10)
            .stale_timeout(45.0)
        )
        if self.proxy:
            client.proxy(self.proxy)

        # 1. Trạng thái kết nối
        @client.on(EventType.connected)
        async def on_connected(evt: TikTokEvent):
            self.room_id = evt.room_id
            self.is_connected = True
            _log.info(f"🟢 [Room @{self.username}] Đã kết nối thành công! Room ID: {self.room_id}")
            await self.broadcast({
                "event": "connected",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {"status": "online", "message": f"Connected to @{self.username}"}
            })

        @client.on(EventType.disconnected)
        async def on_disconnected(evt: TikTokEvent):
            self.is_connected = False
            _log.info(f"🔌 [Room @{self.username}] Đã ngắt kết nối TikTok.")
            await self.broadcast({
                "event": "disconnected",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {"status": "offline", "message": "Disconnected from TikTok Live"}
            })

        @client.on(EventType.reconnecting)
        async def on_reconnecting(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "reconnecting",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": d,
            })

        # 2. Bình luận Chat
        @client.on(EventType.chat)
        async def on_chat(evt: TikTokEvent):
            await self.broadcast({
                "event": "chat",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "comment": evt.comment,
                }
            })

        # 3. Quà Tặng (Gift & Combo Streak)
        @client.on(EventType.gift)
        async def on_gift(evt: TikTokEvent):
            data = evt.data or {}
            streak = self.streak_tracker.process(data)
            gift_obj = data.get("gift") or {}
            await self.broadcast({
                "event": "gift",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "gift": {
                        "id": int(gift_obj.get("id") or 0),
                        "name": evt.gift_name,
                        "diamond_count": int(gift_obj.get("diamond_count") or gift_obj.get("diamondCount") or 0),
                        "image_url": str(gift_obj.get("image", {}).get("url_list", [""])[0]),
                    },
                    "combo": {
                        "streak_id": streak.streak_id,
                        "is_active": streak.is_active,
                        "is_final": streak.is_final,
                        "event_gift_count": streak.event_gift_count,
                        "total_gift_count": streak.total_gift_count,
                        "event_diamond_count": streak.event_diamond_count,
                        "total_diamond_count": streak.total_diamond_count,
                    }
                }
            })

        # 4. Thả Tim (Like)
        @client.on(EventType.like)
        async def on_like(evt: TikTokEvent):
            data = evt.data or {}
            stats = self.like_acc.process(data)
            await self.broadcast({
                "event": "like",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "event_like_count": stats.event_like_count,
                    "total_like_count": stats.total_like_count,
                }
            })

        # 5. Vào phòng / Follow / Share
        @client.on(EventType.join)
        async def on_join(evt: TikTokEvent):
            await self.broadcast({
                "event": "join",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "viewer_count": evt.viewer_count,
                }
            })

        @client.on(EventType.follow)
        async def on_follow(evt: TikTokEvent):
            await self.broadcast({
                "event": "follow",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                }
            })

        @client.on(EventType.share)
        async def on_share(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "share",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "share_target": d.get("share_target") or d.get("shareTarget") or "friends",
                }
            })

        # 6. Thống kê phòng Live (Room User Seq)
        @client.on(EventType.room_user_seq)
        async def on_user_seq(evt: TikTokEvent):
            d = evt.data or {}
            ranks_raw = d.get("ranks_list") or d.get("ranksList") or []
            ranks = []
            for r in ranks_raw[:10]:
                u = r.get("user") or {}
                ranks.append({
                    "nickname": u.get("nickname") or "Anonymous",
                    "score": int(r.get("score") or 0),
                    "rank": int(r.get("rank") or 0),
                })
            await self.broadcast({
                "event": "room_user_seq",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "viewer_count": evt.viewer_count,
                    "total_users": evt.total_users,
                    "top_ranks": ranks,
                }
            })

        # 7. TikTok Shop / Thương Mại Điện Tử (OEC LIVE SHOPPING)
        @client.on(EventType.oec_live_shopping)
        async def on_shopping(evt: TikTokEvent):
            action_type = evt.action_type or 1
            new_pid = evt.product_id
            if new_pid:
                self.active_product_id = new_pid
                action_name = "SetPinProduct (Ghim sản phẩm mới)"
                self.active_product_info = evt.canonical_product_info(region="vn")
            else:
                action_name = "CardRefresh (Duy trì / Làm mới hiển thị thẻ)"

            info = self.active_product_info or evt.canonical_product_info(region="vn", product_id=self.active_product_id)
            pid = self.active_product_id or info.product_id
            canonical_url = info.url or (f"https://shop.tiktok.com/vn/pdp/{pid}" if pid else "")

            await self.broadcast({
                "event": "oec_live_shopping",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "action_type": action_type,
                    "action_name": action_name,
                    "product_id": pid,
                    "product_title": info.title,
                    "product_image": info.image,
                    "product_images": info.images,
                    "product_url": canonical_url,
                    "seller": info.seller,
                    "sold_count": info.sold_count,
                }
            })

        # 8. Đại gia nâng cấp VIP (Privilege Advance)
        @client.on(EventType.privilege_advance)
        async def on_privilege(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "privilege_advance",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "diamond_amount": int(d.get("diamondAmount") or d.get("diamond_amount") or 0),
                    "badge_name": str(d.get("badgeName") or d.get("badge_name") or ""),
                    "privilege_type": str(d.get("privilegeType") or d.get("privilege_type") or ""),
                }
            })

        # 9. Host ghim tin nhắn / Deal (Room Pin)
        @client.on(EventType.room_pin)
        async def on_room_pin(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "room_pin",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "pinned_content": str(d.get("pinnedContent") or d.get("pinned_content") or ""),
                    "pin_id": str(d.get("pinId") or d.get("pin_id") or ""),
                    "action_type": int(d.get("actionType") or d.get("action_type") or 1),
                }
            })

        # 10. Voucher / Banner khuyến mãi (In Room Banner)
        @client.on(EventType.in_room_banner)
        async def on_banner(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "in_room_banner",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "banner_id": str(d.get("bannerId") or d.get("banner_id") or ""),
                    "title": str(d.get("title") or ""),
                    "sub_title": str(d.get("subTitle") or d.get("sub_title") or ""),
                    "image_url": str(d.get("imageUrl") or d.get("image_url") or ""),
                }
            })

        # 11. Mục tiêu phòng Live (Goal Update)
        @client.on(EventType.goal_update)
        async def on_goal(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "goal_update",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "goal_id": str(d.get("goalId") or d.get("goal_id") or ""),
                    "goal_type": str(d.get("goalType") or d.get("goal_type") or ""),
                    "progress": int(d.get("progress") or 0),
                    "target": int(d.get("target") or 0),
                    "contributor_count": int(d.get("contributorCount") or d.get("contributor_count") or 0),
                }
            })

        # 12. Phụ đề lời nói AI thời gian thực (Caption)
        @client.on(EventType.caption)
        async def on_caption(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "caption",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "content": str(d.get("content") or ""),
                    "language": str(d.get("language") or ""),
                }
            })

        # 13. Bao lì xì / Hộp kho báu (Envelope / Treasure Box)
        @client.on(EventType.envelope)
        async def on_envelope(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "envelope",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "treasure_box_id": str(d.get("treasureBoxId") or d.get("treasure_box_id") or ""),
                    "diamond_count": int(d.get("diamondCount") or d.get("diamond_count") or 0),
                    "people_count": int(d.get("peopleCount") or d.get("people_count") or 0),
                }
            })

        # 14. Câu hỏi Q&A mới (Question New)
        @client.on(EventType.question_new)
        async def on_question(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "question_new",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "question_id": str(d.get("questionId") or d.get("question_id") or ""),
                    "question_text": str(d.get("questionText") or d.get("question_text") or d.get("content") or ""),
                }
            })

        # 15. Trận đấu PK Battle (Link Mic Battle)
        @client.on(EventType.link_mic_battle)
        async def on_battle(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "link_mic_battle",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "battle_id": str(d.get("battleId") or d.get("battle_id") or ""),
                    "status": str(d.get("battleStatus") or d.get("battle_status") or "active"),
                }
            })

        # 16. Thông báo Subscriber mới (Sub Notify)
        @client.on(EventType.sub_notify)
        async def on_sub(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "sub_notify",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "sub_month": int(d.get("subMonth") or d.get("sub_month") or 1),
                }
            })

        # 17. Emoji / Sticker Chat (Emote Chat)
        @client.on(EventType.emote_chat)
        async def on_emote(evt: TikTokEvent):
            d = evt.data or {}
            await self.broadcast({
                "event": "emote_chat",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "user": serialize_user(evt),
                    "emote_id": str(d.get("emoteId") or d.get("emote_id") or ""),
                    "image_url": str(d.get("imageUrl") or d.get("image_url") or ""),
                }
            })

        # 18. Sự kiện mở rộng chưa ánh xạ (Unknown fallback - Đảm bảo ZERO loss)
        @client.on(EventType.unknown)
        async def on_unknown(evt: TikTokEvent):
            await self.broadcast({
                "event": "unknown",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "raw_type": getattr(evt, "raw_type", "unknown"),
                    "payload": evt.data if isinstance(evt.data, dict) else {},
                }
            })

        # 19. Phòng Live kết thúc
        @client.on(EventType.live_ended)
        async def on_live_ended(evt: TikTokEvent):
            _log.info(f"🛑 [Room @{self.username}] Buổi livestream đã kết thúc.")
            await self.broadcast({
                "event": "live_ended",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {"status": "ended", "message": "The live stream has ended."}
            })

        # Chạy vòng lặp kết nối và bắt lỗi cấu trúc chuẩn
        try:
            await client.connect()
        except Exception as e:
            _log.error(f"❌ [Room @{self.username}] Lỗi client: {e}")
            err_str = str(e)
            
            # Phân loại mã lỗi chuẩn cho các hệ thống bên ngoài dễ xử lý
            if isinstance(e, HostNotOnlineError) or "not currently live" in err_str.lower():
                code = "HOST_NOT_ONLINE"
                msg = f"Streamer @{self.username} hiện không phát sóng trực tiếp."
            elif isinstance(e, UserNotFoundError) or "does not exist" in err_str.lower():
                code = "USER_NOT_FOUND"
                msg = f"Không tìm thấy tài khoản TikTok @{self.username}."
            elif isinstance(e, DeviceBlockedError) or "DEVICE_BLOCKED" in err_str or "415" in err_str:
                code = "DEVICE_BLOCKED"
                msg = "Thiết bị bị TikTok cắm cờ (HTTP 415), client đang tự động cấp lại token mới."
            elif "429" in err_str or "Too Many Requests" in err_str:
                code = "RATE_LIMITED"
                msg = "Quá nhiều kết nối trên cùng một địa chỉ IP (HTTP 429)."
            elif isinstance(e, TikTokBlockedError) or "403" in err_str or "Forbidden" in err_str:
                code = "IP_BLOCKED"
                msg = "Địa chỉ IP bị tường lửa TikTok chặn (HTTP 403)."
            elif isinstance(e, AgeRestrictedError) or "age-restricted" in err_str:
                code = "AGE_RESTRICTED"
                msg = "Phòng Live giới hạn độ tuổi 18+ (cần session cookie)."
            elif "Timeout" in err_str:
                code = "NETWORK_TIMEOUT"
                msg = "Kết nối tới máy chủ TikTok bị quá thời gian chờ (Timeout)."
            else:
                code = type(e).__name__
                msg = err_str

            await self.broadcast({
                "event": "error",
                "username": self.username,
                "room_id": self.room_id,
                "timestamp": get_iso_time(),
                "data": {
                    "code": code,
                    "message": msg,
                    "raw_error": err_str,
                }
            })


class GatewayManager:
    """Quản lý toàn bộ danh sách phòng và định tuyến các client WebSocket."""

    def __init__(self, proxy: str = "", idle_timeout: float = 30.0):
        self.proxy = proxy
        self.idle_timeout = idle_timeout
        self.rooms: Dict[str, RoomHub] = {}
        self.master_ttwid: str = ""
        self.start_time = time.time()
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Khởi tạo cấp Master TTWID từ Playwright hoặc Cache."""
        _log.info("🔑 Đang chuẩn bị token TTWID xác thực an toàn qua Playwright...")
        try:
            self.master_ttwid = get_ttwid("tiktok", proxy=self.proxy)
            _log.info(f"✅ Đã chuẩn bị TTWID thành công: {self.master_ttwid[:20]}...")
        except Exception as e:
            _log.warning(f"⚠️ Cảnh báo khởi tạo TTWID: {e}")
            self.master_ttwid = ""

    async def get_or_create_room(self, username: str) -> RoomHub:
        clean_user = username.strip().lstrip("@").lower()
        async with self._lock:
            if clean_user not in self.rooms:
                hub = RoomHub(clean_user, proxy=self.proxy, idle_timeout=self.idle_timeout)
                hub.start_worker(self.master_ttwid)
                self.rooms[clean_user] = hub
            return self.rooms[clean_user]

    async def cleanup_idle_rooms(self):
        """Vòng lặp dọn dẹp các phòng không còn client nào xem sau idle_timeout."""
        while True:
            await asyncio.sleep(10)
            async with self._lock:
                to_delete = []
                for user, hub in list(self.rooms.items()):
                    if hub.should_cleanup():
                        to_delete.append(user)

                for user in to_delete:
                    _log.info(f"🧹 Dọn dẹp phòng @{user} do không còn client nào theo dõi.")
                    hub = self.rooms.pop(user)
                    await hub.stop()

    def list_rooms_info(self) -> List[Dict[str, Any]]:
        info = []
        for user, hub in self.rooms.items():
            info.append({
                "username": user,
                "room_id": hub.room_id,
                "is_connected": hub.is_connected,
                "clients_count": len(hub.clients),
                "active_product_id": hub.active_product_id,
                "total_broadcasts": hub.total_broadcasts,
                "uptime_seconds": int(time.time() - hub.created_at),
            })
        return info

    def get_gateway_stats(self) -> Dict[str, Any]:
        total_clients = sum(len(h.clients) for h in self.rooms.values())
        total_events = sum(h.total_broadcasts for h in self.rooms.values())
        return {
            "active_rooms": len(self.rooms),
            "total_connected_clients": total_clients,
            "total_events_broadcasted": total_events,
            "server_uptime_seconds": int(time.time() - self.start_time),
        }


async def handle_connection(ws: ServerConnection, manager: GatewayManager):
    """Xử lý vòng đời kết nối của một WebSocket Client bên ngoài."""
    subscribed_rooms: Set[str] = set()

    # 1. Kiểm tra Query Param từ Request URI (vd: /live?username=swatchesbybaobao)
    req_path = ws.request.path if hasattr(ws, "request") and ws.request else "/"
    parsed_url = urllib.parse.urlparse(req_path)
    params = urllib.parse.parse_qs(parsed_url.query)
    
    initial_user = params.get("username", [None])[0] or params.get("room", [None])[0]
    if initial_user:
        hub = await manager.get_or_create_room(initial_user)
        hub.add_client(ws)
        subscribed_rooms.add(hub.username)
        await ws.send(json.dumps({
            "event": "subscribed",
            "username": hub.username,
            "room_id": hub.room_id,
            "status": "online" if hub.is_connected else "connecting",
            "message": f"Successfully subscribed to @{hub.username}",
            "timestamp": get_iso_time(),
        }, ensure_ascii=False))

    try:
        async for message in ws:
            try:
                cmd = json.loads(message)
            except Exception:
                await ws.send(json.dumps({
                    "event": "error",
                    "data": {"code": "INVALID_JSON", "message": "Invalid JSON message format"},
                    "timestamp": get_iso_time(),
                }))
                continue

            action = cmd.get("action", "").lower()

            if action == "subscribe":
                target_user = cmd.get("username") or cmd.get("room")
                if not target_user:
                    await ws.send(json.dumps({
                        "event": "error",
                        "data": {"code": "MISSING_PARAM", "message": "Missing 'username' parameter in subscribe action"},
                        "timestamp": get_iso_time(),
                    }))
                    continue

                hub = await manager.get_or_create_room(target_user)
                hub.add_client(ws)
                subscribed_rooms.add(hub.username)
                await ws.send(json.dumps({
                    "event": "subscribed",
                    "username": hub.username,
                    "room_id": hub.room_id,
                    "status": "online" if hub.is_connected else "connecting",
                    "message": f"Successfully subscribed to @{hub.username}",
                    "timestamp": get_iso_time(),
                }, ensure_ascii=False))

            elif action == "unsubscribe":
                target_user = cmd.get("username") or cmd.get("room")
                if target_user:
                    clean_u = target_user.strip().lstrip("@").lower()
                    if clean_u in manager.rooms:
                        manager.rooms[clean_u].remove_client(ws)
                    subscribed_rooms.discard(clean_u)
                    await ws.send(json.dumps({
                        "event": "unsubscribed",
                        "username": clean_u,
                        "timestamp": get_iso_time(),
                    }))

            elif action == "get_room_status":
                target_user = cmd.get("username") or cmd.get("room")
                if target_user:
                    clean_u = target_user.strip().lstrip("@").lower()
                    hub = manager.rooms.get(clean_u)
                    if hub:
                        await ws.send(json.dumps({
                            "event": "room_status",
                            "username": clean_u,
                            "room_id": hub.room_id,
                            "is_connected": hub.is_connected,
                            "clients_count": len(hub.clients),
                            "active_product_id": hub.active_product_id,
                            "total_broadcasts": hub.total_broadcasts,
                            "uptime_seconds": int(time.time() - hub.created_at),
                            "timestamp": get_iso_time(),
                        }, ensure_ascii=False))
                    else:
                        await ws.send(json.dumps({
                            "event": "room_status",
                            "username": clean_u,
                            "is_connected": False,
                            "clients_count": 0,
                            "message": "Room is not active",
                            "timestamp": get_iso_time(),
                        }))

            elif action == "list_rooms":
                rooms_info = manager.list_rooms_info()
                await ws.send(json.dumps({
                    "event": "rooms_list",
                    "rooms": rooms_info,
                    "total_active_rooms": len(rooms_info),
                    "timestamp": get_iso_time(),
                }, ensure_ascii=False))

            elif action == "stats":
                stats_info = manager.get_gateway_stats()
                await ws.send(json.dumps({
                    "event": "gateway_stats",
                    "data": stats_info,
                    "timestamp": get_iso_time(),
                }, ensure_ascii=False))

            elif action == "ping":
                await ws.send(json.dumps({
                    "event": "pong",
                    "server_time": get_iso_time(),
                }))

            else:
                await ws.send(json.dumps({
                    "event": "error",
                    "data": {"code": "UNKNOWN_ACTION", "message": f"Unknown action: '{action}'"},
                    "timestamp": get_iso_time(),
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Khi client ngắt kết nối, dọn dẹp khỏi các phòng đã đăng ký
        for r_user in subscribed_rooms:
            if r_user in manager.rooms:
                manager.rooms[r_user].remove_client(ws)


async def main():
    parser = argparse.ArgumentParser(description="TikTok Live WebSocket Gateway Server")
    parser.add_argument("--host", default="0.0.0.0", help="IP Host lắng nghe (mặc định: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=8765, help="Cổng WebSocket (mặc định: 8765)")
    parser.add_argument("--proxy", default="", help="Proxy cho TikTokLiveClient (vd: 'http://127.0.0.1:8080')")
    parser.add_argument("--idle-timeout", type=float, default=30.0, help="Thời gian chờ ngắt phòng khi không có client (giây)")
    args = parser.parse_args()

    manager = GatewayManager(proxy=args.proxy, idle_timeout=args.idle_timeout)
    await manager.initialize()

    # Chạy task dọn dẹp phòng ngầm
    asyncio.create_task(manager.cleanup_idle_rooms())

    print("\n" + "=" * 90)
    print("🌐 TIKTOK LIVE WEBSOCKET GATEWAY SERVER ĐANG CHẠY")
    print(f"🚀 Địa chỉ lắng nghe: ws://{args.host}:{args.port}")
    print(f"📌 Cách kết nối nhanh: ws://localhost:{args.port}/live?username=<streamer_username>")
    print(f"📦 Hỗ trợ 100% sự kiện: Chat, Gift (Combo Delta), Like, TikTok Shop PDP, Badges, Captions...")
    print("=" * 90 + "\n")

    async def handler(ws: ServerConnection):
        await handle_connection(ws, manager)

    async with serve(handler, args.host, args.port):
        await asyncio.get_running_loop().create_future()  # Chạy mãi mãi


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[🛑 STOPPED] Đã dừng WebSocket Gateway Server.")

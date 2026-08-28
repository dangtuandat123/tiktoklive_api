from typing import Any, NamedTuple


class EventType:
    # Control
    connected = "connected"
    disconnected = "disconnected"
    reconnecting = "reconnecting"
    unknown = "unknown"

    # core
    chat = "chat"
    gift = "gift"
    like = "like"
    member = "member"
    social = "social"
    room_user_seq = "room_user_seq"
    control = "control"

    # Sub-routed convenience
    follow = "follow"
    share = "share"
    join = "join"
    live_ended = "live_ended"

    # useful
    live_intro = "live_intro"
    room_message = "room_message"
    caption = "caption"
    goal_update = "goal_update"
    im_delete = "im_delete"

    # niche + extended
    rank_update = "rank_update"
    poll = "poll"
    envelope = "envelope"
    room_pin = "room_pin"
    unauthorized_member = "unauthorized_member"
    link_mic_method = "link_mic_method"
    link_mic_battle = "link_mic_battle"
    link_mic_armies = "link_mic_armies"
    link_message = "link_message"
    link_layer = "link_layer"
    link_mic_layout_state = "link_mic_layout_state"
    gift_panel_update = "gift_panel_update"
    in_room_banner = "in_room_banner"
    guide = "guide"
    emote_chat = "emote_chat"
    question_new = "question_new"
    sub_notify = "sub_notify"
    barrage = "barrage"
    hourly_rank = "hourly_rank"
    msg_detect = "msg_detect"
    link_mic_fan_ticket = "link_mic_fan_ticket"
    room_verify = "room_verify"
    oec_live_shopping = "oec_live_shopping"
    gift_broadcast = "gift_broadcast"
    rank_text = "rank_text"
    gift_dynamic_restriction = "gift_dynamic_restriction"
    viewer_picks_update = "viewer_picks_update"
    privilege_advance = "privilege_advance"


    # secondary
    access_control = "access_control"
    access_recall = "access_recall"
    alert_box_audit_result = "alert_box_audit_result"
    binding_gift = "binding_gift"
    boost_card = "boost_card"
    bottom = "bottom"
    game_rank_notify = "game_rank_notify"
    gift_prompt = "gift_prompt"
    link_state = "link_state"
    link_mic_battle_punish_finish = "link_mic_battle_punish_finish"
    linkmic_battle_task = "linkmic_battle_task"
    marquee_announcement = "marquee_announcement"
    notice = "notice"
    notify = "notify"
    partnership_drops_update = "partnership_drops_update"
    partnership_game_offline = "partnership_game_offline"
    partnership_punish = "partnership_punish"
    perception = "perception"
    speaker = "speaker"
    sub_capsule = "sub_capsule"
    sub_pin_event = "sub_pin_event"
    subscription_notify = "subscription_notify"
    toast = "toast"
    system = "system"
    live_game_intro = "live_game_intro"


class TikTokEvent(NamedTuple):
    type: str
    data: Any
    room_id: str = ""

    @property
    def user(self) -> dict:
        """Trích xuất dictionary thông tin User nếu có."""
        if isinstance(self.data, dict):
            return self.data.get("user") or {}
        return {}

    @property
    def user_nickname(self) -> str:
        """Tên hiển thị / Nickname của người gửi sự kiện."""
        u = self.user
        return str(u.get("nickname") or u.get("nickName") or u.get("unique_id") or "")

    @property
    def user_id(self) -> str:
        """ID định danh của người dùng."""
        u = self.user
        return str(u.get("id") or "")

    @property
    def comment(self) -> str:
        """Nội dung bình luận / tin nhắn chat."""
        if isinstance(self.data, dict):
            return str(self.data.get("content") or self.data.get("comment") or "")
        return ""

    @property
    def gift_name(self) -> str:
        """Tên quà tặng nếu là sự kiện Gift."""
        if isinstance(self.data, dict):
            return str(self.data.get("gift", {}).get("name") or "")
        return ""

    @property
    def repeat_count(self) -> int:
        """Số lượng quà trong combo nếu là sự kiện Gift."""
        if isinstance(self.data, dict):
            return int(self.data.get("repeat_count") or self.data.get("repeatCount") or 1)
        return 1

    @property
    def diamond_count(self) -> int:
        """Tổng số kim cương/xu nếu là sự kiện Gift."""
        if isinstance(self.data, dict):
            return int(self.data.get("diamond_total") or self.data.get("gift", {}).get("diamondCount") or 0)
        return 0

    @property
    def user_unique_id(self) -> str:

        """Tên tài khoản duy nhất (TikTok Handle) của người dùng."""
        u = self.user
        return str(u.get("unique_id") or u.get("uniqueId") or "")

    @property
    def sec_uid(self) -> str:
        """Mã SecUID bảo mật của người dùng."""
        u = self.user
        return str(u.get("sec_uid") or u.get("secUid") or "")

    @property
    def avatar_url(self) -> str:
        """Đường dẫn URL ảnh đại diện của người dùng."""
        u = self.user
        thumb = u.get("avatar_thumb") or u.get("avatarThumb") or {}
        urls = thumb.get("url_list") or thumb.get("urlList") or []
        return str(urls[0]) if urls else ""

    @property
    def like_count(self) -> int:
        """Số lượt tim vừa thả nếu là sự kiện Like."""
        if isinstance(self.data, dict):
            return int(self.data.get("count") or 1)
        return 1

    @property
    def total_likes(self) -> int:
        """Tổng số tim tích lũy toàn phòng nếu là sự kiện Like."""
        if isinstance(self.data, dict):
            return int(self.data.get("total") or 0)
        return 0

    @property
    def viewer_count(self) -> int:
        """Số người đang xem trực tiếp nếu là sự kiện Thống kê / Vào phòng."""
        if isinstance(self.data, dict):
            return int(self.data.get("viewerCount") or self.data.get("viewer_count") or self.data.get("memberCount") or self.data.get("member_count") or 0)
        return 0

    @property
    def total_users(self) -> int:
        """Tổng lượt người đã ghé qua phòng nếu là sự kiện Thống kê."""
        if isinstance(self.data, dict):
            return int(self.data.get("totalUser") or self.data.get("total_user") or 0)
        return 0

    @property
    def product_id(self) -> str:
        """Mã Sản Phẩm (Product ID) nếu là sự kiện TikTok Shop."""
        if isinstance(self.data, dict):
            raw = self.data.get("productIdRaw") or self.data.get("product_id_raw") or self.data.get("product_id")
            if raw:
                import base64, io
                try:
                    raw_bytes = base64.b64decode(raw) if isinstance(raw, str) else raw
                    stream = io.BytesIO(raw_bytes)
                    
                    def decode_varint(s):
                        res, shift = 0, 0
                        while True:
                            b = s.read(1)
                            if not b:
                                return None
                            byte = b[0]
                            res |= (byte & 0x7F) << shift
                            if not (byte & 0x80):
                                break
                            shift += 7
                        return res

                    while True:
                        tag = decode_varint(stream)
                        if tag is None:
                            break
                        wire = tag & 0x07
                        if wire == 0:
                            val = decode_varint(stream)
                            if val and val > 1000000000:
                                return str(val)
                        elif wire == 2:
                            l = decode_varint(stream)
                            if l:
                                stream.read(l)
                        elif wire == 1:
                            stream.read(8)
                        elif wire == 5:
                            stream.read(4)
                except Exception:
                    pass
            return str(self.data.get("product_id") or "")
        return ""

    @property
    def product_url(self) -> str:
        """Đường dẫn link mở sản phẩm trực tiếp trên TikTok Shop (không bị Captcha)."""
        pid = self.product_id
        return f"https://shop.tiktok.com/vn/pdp/{pid}" if pid else ""

    def canonical_product_info(self, region: str = "vn") -> tuple[str, str]:
        """Tự động resolve link SEO hoàn chỉnh và trích xuất tên sản phẩm từ URL slug."""
        pid = self.product_id
        if not pid:
            return "", ""
        from curl_cffi import requests
        import urllib.parse
        url = f"https://shop.tiktok.com/{region.lower()}/pdp/{pid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        }
        try:
            r = requests.get(url, headers=headers, impersonate="chrome120", allow_redirects=False, timeout=4)
            canonical = r.headers.get("Location") or url
            parsed = urllib.parse.urlparse(canonical)
            parts = [p for p in parsed.path.split("/") if p and p not in (region.lower(), "pdp", pid)]
            title = parts[0].replace("-", " ").title() if parts else ""
            return canonical, title
        except Exception:
            return url, ""

    @property
    def action_type(self) -> int:
        """Mã hành động nếu là sự kiện OEC Shopping / Member / Control."""
        if isinstance(self.data, dict):
            return int(self.data.get("actionType") or self.data.get("action_type") or self.data.get("action") or 0)
        return 0



    @property
    def is_host(self) -> bool:
        """Khán giả có phải là Streamer / Chủ phòng hay không."""
        ident = self.user.get("user_identity") or self.user.get("userIdentity") or {}
        return bool(ident.get("is_anchor") or ident.get("isAnchor"))

    @property
    def is_mod(self) -> bool:
        """Khán giả có phải là Quản trị viên (Moderator) hay không."""
        ident = self.user.get("user_identity") or self.user.get("userIdentity") or {}
        return bool(ident.get("is_moderator") or ident.get("isModerator"))

    @property
    def is_sub(self) -> bool:
        """Khán giả có phải là Hội viên trả phí (Subscriber) hay không."""
        ident = self.user.get("user_identity") or self.user.get("userIdentity") or {}
        return bool(ident.get("is_subscriber") or ident.get("isSubscriber"))

    @property
    def is_fan(self) -> bool:
        """Khán giả có tham gia Câu lạc bộ Fan Club hay không."""
        fc = self.user.get("fans_club_info") or self.user.get("fansClubInfo") or {}
        return bool(fc.get("club_name") or fc.get("clubName"))

    @property
    def fans_club_name(self) -> str:
        """Tên câu lạc bộ Fan Club của người dùng."""
        fc = self.user.get("fans_club_info") or self.user.get("fansClubInfo") or {}
        return str(fc.get("club_name") or fc.get("clubName") or "")

    @property
    def fans_club_level(self) -> int:
        """Cấp độ Fan Club của người dùng."""
        fc = self.user.get("fans_club_info") or self.user.get("fansClubInfo") or {}
        return int(fc.get("level") or 0)



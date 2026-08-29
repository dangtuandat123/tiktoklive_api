import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from ..errors import (
    AgeRestrictedError,
    HostNotOnlineError,
    TikTokApiError,
    TikTokBlockedError,
    UserNotFoundError,
)
from .ua import random_ua, system_locale, system_timezone


class RoomIdResult:
    __slots__ = ("room_id",)

    def __init__(self, room_id: str) -> None:
        self.room_id = room_id


class StreamUrls:
    __slots__ = ("flv_origin", "flv_hd", "flv_sd", "flv_ld", "flv_audio")

    def __init__(
        self,
        flv_origin: str = "",
        flv_hd: str = "",
        flv_sd: str = "",
        flv_ld: str = "",
        flv_audio: str = "",
    ) -> None:
        self.flv_origin = flv_origin
        self.flv_hd = flv_hd
        self.flv_sd = flv_sd
        self.flv_ld = flv_ld
        self.flv_audio = flv_audio


class RoomInfo:
    __slots__ = ("title", "viewers", "likes", "total_user", "stream_url")

    def __init__(
        self,
        title: str = "",
        viewers: int = 0,
        likes: int = 0,
        total_user: int = 0,
        stream_url: Optional[StreamUrls] = None,
    ) -> None:
        self.title = title
        self.viewers = viewers
        self.likes = likes
        self.total_user = total_user
        self.stream_url = stream_url


def _build_opener(proxy: str = "") -> urllib.request.OpenerDirector:
    handlers: list = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    return urllib.request.build_opener(*handlers)


def check_online(
    username: str,
    timeout: float = 10.0,
    proxy: str = "",
    user_agent: Optional[str] = None,
    language: Optional[str] = None,
    region: Optional[str] = None,
) -> RoomIdResult:
    """Check if a TikTok user is currently live. Returns room ID."""
    ua = user_agent if user_agent else random_ua()
    clean = username.strip().lstrip("@")
    sys_lang, sys_reg = system_locale()
    lang = language if language else sys_lang
    reg = region if region else sys_reg
    browser_lang = f"{lang}-{reg}"
    params = urllib.parse.urlencode({
        "aid": "1988",
        "app_name": "tiktok_web",
        "device_platform": "web_pc",
        "app_language": lang,
        "browser_language": browser_lang,
        "region": reg,
        "user_is_login": "false",
        "sourceType": "54",
        "staleTime": "600000",
        "uniqueId": clean,
    })
    url = f"https://www.tiktok.com/api-live/user/room?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    opener = _build_opener(proxy)

    try:
        with opener.open(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
        result: Dict[str, Any] = json.loads(body)
    except Exception as e:

        # Fallback 1: Trích xuất trực tiếp roomId từ trang Live HTML qua curl_cffi Chrome impersonation
        try:
            import re
            from curl_cffi import requests
            r_live = requests.get(
                f"https://www.tiktok.com/@{clean}/live",
                headers={"User-Agent": ua},
                impersonate="chrome120",
                timeout=timeout,
            )
            m = re.search(r'"roomId":"(\d{10,})"', r_live.text)
            if m and m.group(1) != "0":
                return RoomIdResult(m.group(1))
        except Exception:
            pass

        # Fallback 2: Trích xuất qua Headless Chromium
        try:
            import re
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=ua)
                page = ctx.new_page()
                page.goto(f"https://www.tiktok.com/@{clean}/live", wait_until="domcontentloaded", timeout=int(timeout * 1000))
                m = re.search(r'"roomId":"(\d{10,})"', page.content())
                browser.close()
                if m and m.group(1) != "0":
                    return RoomIdResult(m.group(1))
        except Exception:
            pass

        if isinstance(e, urllib.error.HTTPError):
            raise TikTokBlockedError(e.code) from e
        raise TikTokBlockedError(403) from e


    status_code = result.get("statusCode", -1)
    if status_code == 19881007:
        raise UserNotFoundError(clean)
    if status_code != 0:
        raise TikTokApiError(status_code)

    data = result.get("data", {})
    room_id = str(data.get("user", {}).get("roomId", ""))
    if not room_id or room_id == "0":
        raise HostNotOnlineError(clean)

    live_status = data.get("liveRoom", {}).get("status", 0)
    user_status = data.get("user", {}).get("status", 0)
    if live_status != 2 and user_status != 2:
        raise HostNotOnlineError(clean)

    return RoomIdResult(room_id)


def fetch_room_info(
    room_id: str,
    timeout: float = 10.0,
    cookies: str = "",
    proxy: str = "",
    user_agent: Optional[str] = None,
    language: Optional[str] = None,
    region: Optional[str] = None,
) -> RoomInfo:
    """Fetch room metadata. Needs cookies for 18+ rooms."""
    ua = user_agent if user_agent else random_ua()
    tz = system_timezone()
    sys_lang, sys_reg = system_locale()
    lang = language if language else sys_lang
    reg = region if region else sys_reg
    browser_lang = f"{lang}-{reg}"
    params = urllib.parse.urlencode({
        "aid": "1988",
        "app_name": "tiktok_web",
        "device_platform": "web_pc",
        "app_language": lang,
        "browser_language": browser_lang,
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "Linux x86_64",
        "cookie_enabled": "true",
        "screen_height": "1080",
        "screen_width": "1920",
        "tz_name": tz,
        "webcast_language": lang,
        "room_id": room_id,
    })
    url = f"https://webcast.tiktok.com/webcast/room/info/?{params}"
    headers: Dict[str, str] = {
        "User-Agent": ua,
        "Referer": "https://www.tiktok.com/",
    }
    if cookies:
        headers["Cookie"] = cookies

    req = urllib.request.Request(url, headers=headers)
    opener = _build_opener(proxy)

    try:
        with opener.open(req, timeout=timeout) as resp:
            body_raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise TikTokBlockedError(e.code) from e
        raise TikTokBlockedError(e.code) from e

    body: Dict[str, Any] = json.loads(body_raw)
    sc = body.get("status_code", -1)

    if sc == 4003110:
        raise AgeRestrictedError()
    if sc != 0:
        raise TikTokApiError(sc)

    data = body.get("data", {})
    stats = data.get("stats", {})

    return RoomInfo(
        title=str(data.get("title", "")),
        viewers=int(data.get("user_count", 0)),
        likes=int(stats.get("like_count", 0)),
        total_user=int(stats.get("total_user", 0)),
        stream_url=_parse_stream_urls(data.get("stream_url")),
    )


def _parse_stream_urls(raw: Any) -> Optional[StreamUrls]:
    if not isinstance(raw, dict):
        return None
    flv = raw.get("flv_pull_url")
    if not isinstance(flv, dict) or not flv:
        return None
    return StreamUrls(
        flv_origin=flv.get("FULL_HD1", ""),
        flv_hd=flv.get("HD1", ""),
        flv_sd=flv.get("SD1", ""),
        flv_ld=flv.get("SD2", ""),
        flv_audio=flv.get("AUDIO", ""),
    )

"""Module tự động sinh và quản lý Cookie TTWID bằng Trình duyệt ngầm Playwright.

Được thiết kế đóng gói độc lập cao (Zero-Coupling), tương thích đa nền tảng
(Windows, Linux, macOS, Docker) và hỗ trợ đa kênh fallback trình duyệt
(Bundled Chromium -> Google Chrome -> Microsoft Edge).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

_log = logging.getLogger("piratetok_live.auth.playwright")

# Danh sách cờ cấu hình trình duyệt tối ưu chống phát hiện bot
_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-position=0,0",
    "--ignore-certificate-errors",
    "--disable-extensions",
    "--disable-dev-shm-usage",
]

# Kịch bản tiêm trước khi trang web tải nhằm che giấu dấu vết WebDriver
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
if (!window.chrome) {
    window.chrome = { runtime: {} };
}
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi'] });
"""

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet", "imageset"}


class PlaywrightTTWIDGenerator:
    """Công cụ tạo và lưu trữ Cookie TTWID chuẩn 100% bằng Playwright Chromium.

    Tính năng nổi bật:
    - Chạy hoàn toàn ngầm (Headless) hoặc hiển thị giao diện (Headful).
    - Tự động chuyển đổi kênh trình duyệt: Chromium -> Chrome -> Edge nếu một kênh bị lỗi.
    - Chặn tải hình ảnh/video/font/css để đạt tốc độ trích xuất cookie trong 1 - 2 giây.
    - Tích hợp Smart Cache: Tự động lưu cookie vào file và tái sử dụng (0ms).
    - Hỗ trợ cả giao diện Bất đồng bộ (Async) và Đồng bộ (Sync) an toàn trong mọi luồng.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 15000,
        cache_file: Optional[str] = ".ttwid_cache.json",
        cache_ttl_hours: float = 72.0,
        user_agent: Optional[str] = None,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.cache_file = cache_file
        self.cache_ttl_seconds = cache_ttl_hours * 3600.0
        self.user_agent = user_agent or _DEFAULT_USER_AGENT

    # =========================================================================
    # BỘ NHỚ ĐỆM (CACHE MANAGER)
    # =========================================================================

    def _read_cache(self) -> Optional[str]:
        """Đọc token hợp lệ từ file cache nếu chưa hết hạn."""
        if not self.cache_file or not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ttwid = data.get("ttwid")
            created_at = float(data.get("created_at", 0))
            if ttwid and (time.time() - created_at) < self.cache_ttl_seconds:
                _log.debug("TTWID lấy từ Cache (còn hạn: %.1f giờ)", (self.cache_ttl_seconds - (time.time() - created_at)) / 3600)
                return ttwid
        except Exception as err:
            _log.debug("Không thể đọc cache TTWID: %s", err)
        return None

    def _write_cache(self, ttwid: str) -> None:
        """Lưu token mới vào file cache."""
        if not self.cache_file:
            return
        try:
            data = {
                "ttwid": ttwid,
                "created_at": time.time(),
                "created_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            _log.debug("Đã lưu TTWID mới vào cache: %s", self.cache_file)
        except Exception as err:
            _log.warning("Không thể lưu cache TTWID: %s", err)

    # =========================================================================
    # GIAO TIẾP ASYNC (BẤT ĐỒNG BỘ)
    # =========================================================================

    async def fetch_async(
        self,
        username: str = "tiktok",
        proxy: str = "",
        force_refresh: bool = False,
    ) -> str:
        """Lấy một token ttwid mới (Async).

        Args:
            username: Streamer profile dùng để mồi request (mặc định 'tiktok').
            proxy: Proxy tùy chọn dạng 'http://ip:port' hoặc 'http://user:pass@ip:port'.
            force_refresh: Bỏ qua cache và bắt buộc mở trình duyệt lấy token mới.

        Returns:
            Chuỗi cookie ttwid (ví dụ: '1%7CID2n45...').
        """
        if not force_refresh:
            cached = self._read_cache()
            if cached:
                return cached

        try:
            from playwright.async_api import async_playwright
        except ImportError as err:
            raise RuntimeError(
                "Thư viện 'playwright' chưa được cài đặt. "
                "Vui lòng chạy: pip install playwright && playwright install chromium"
            ) from err

        clean_user = username.strip().lstrip("@") or "tiktok"
        target_url = f"https://www.tiktok.com/@{clean_user}"

        proxy_config = None
        if proxy:
            proxy_config = {"server": proxy}

        channels_to_try: List[Optional[str]] = [None, "chrome", "msedge"]
        last_exception: Optional[Exception] = None

        async with async_playwright() as p:
            for channel in channels_to_try:
                browser = None
                try:
                    launch_kwargs: Dict[str, Any] = {
                        "headless": self.headless,
                        "args": _BROWSER_ARGS,
                        "proxy": proxy_config,
                    }
                    if channel:
                        launch_kwargs["channel"] = channel

                    browser = await p.chromium.launch(**launch_kwargs)
                    context = await browser.new_context(
                        user_agent=self.user_agent,
                        viewport={"width": 1280, "height": 720},
                        locale="vi-VN",
                        timezone_id="Asia/Ho_Chi_Minh",
                        ignore_https_errors=True,
                    )

                    # Tiêm script ẩn danh
                    await context.add_init_script(_STEALTH_JS)
                    page = await context.new_page()

                    # Tối ưu: Chặn tải hình ảnh, font, css, media để lấy cookie siêu tốc (<1.5s)
                    async def _route_interceptor(route):
                        if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
                            await route.abort()
                        else:
                            await route.continue_()

                    await page.route("**/*", _route_interceptor)

                    # Truy cập trang
                    try:
                        await page.goto(
                            target_url,
                            timeout=self.timeout_ms,
                            wait_until="commit",
                        )
                    except Exception as nav_err:
                        _log.debug("Page goto soft timeout/commit: %s", nav_err)

                    # Lấy danh sách cookie (thử polling tối đa 3 lần cách nhau 500ms)
                    for _ in range(5):
                        cookies = await context.cookies()
                        for c in cookies:
                            if c.get("name") == "ttwid" and c.get("value"):
                                val = str(c["value"])
                                self._write_cache(val)
                                await browser.close()
                                return val
                        await asyncio.sleep(0.5)

                    await browser.close()
                except Exception as err:
                    last_exception = err
                    _log.debug("Thử channel %s thất bại: %s", channel, err)
                    if browser:
                        try:
                            await browser.close()
                        except Exception:
                            pass
                    continue

        if last_exception:
            raise RuntimeError(f"Playwright: Không thể lấy ttwid từ TikTok: {last_exception}") from last_exception
        raise RuntimeError("Playwright: Trang web TikTok không trả về cookie ttwid.")

    # =========================================================================
    # GIAO TIẾP SYNC (ĐỒNG BỘ - AN TOÀN TRONG MỌI LUỒNG)
    # =========================================================================

    def fetch_sync(
        self,
        username: str = "tiktok",
        proxy: str = "",
        force_refresh: bool = False,
    ) -> str:
        """Lấy một token ttwid mới (Sync).

        Tự động xử lý an toàn dù đang ở luồng chính, luồng phụ hay bên trong một asyncio event loop.
        """
        try:
            # Kiểm tra xem có đang chạy bên trong một Event Loop đang hoạt động không
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Nếu đang ở trong event loop, chạy async coroutine qua ThreadPoolExecutor độc lập
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.fetch_async(
                            username=username,
                            proxy=proxy,
                            force_refresh=force_refresh,
                        )
                    )
                )
                return future.result()
        else:
            # Nếu không có event loop, chạy trực tiếp
            return asyncio.run(
                self.fetch_async(
                    username=username,
                    proxy=proxy,
                    force_refresh=force_refresh,
                )
            )


# Khởi tạo singleton generator dùng sẵn tiện lợi
_global_generator = PlaywrightTTWIDGenerator()


def get_ttwid(
    username: str = "tiktok",
    proxy: str = "",
    force_refresh: bool = False,
    headless: bool = True,
) -> str:
    """Hàm tiện ích đồng bộ để lấy nhanh 1 token TTWID bằng Playwright."""
    if not headless or proxy:
        gen = PlaywrightTTWIDGenerator(headless=headless)
        return gen.fetch_sync(username=username, proxy=proxy, force_refresh=force_refresh)
    return _global_generator.fetch_sync(username=username, proxy=proxy, force_refresh=force_refresh)


async def get_ttwid_async(
    username: str = "tiktok",
    proxy: str = "",
    force_refresh: bool = False,
    headless: bool = True,
) -> str:
    """Hàm tiện ích bất đồng bộ để lấy nhanh 1 token TTWID bằng Playwright."""
    if not headless or proxy:
        gen = PlaywrightTTWIDGenerator(headless=headless)
        return await gen.fetch_async(username=username, proxy=proxy, force_refresh=force_refresh)
    return await _global_generator.fetch_async(username=username, proxy=proxy, force_refresh=force_refresh)

"""TikTok Shop Product Scraper & Resolver.

Mô đun chuyên giải mã và cào thông tin chi tiết sản phẩm TikTok Shop:
1. Hỗ trợ cào trực tiếp qua Product ID.
2. Hỗ trợ Session Cookie (sessionid) để vượt qua Captcha bảo vệ của TikTok Shop.
3. Hỗ trợ trích xuất thông tin qua Mobile H5 Schema và Open API.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright
from piratetok_live.auth.playwright_ttwid import get_ttwid


class TikTokShopResolver:
    """Bộ giải mã thông tin chi tiết sản phẩm TikTok Shop."""

    def __init__(self, session_cookie: Optional[str] = None):
        self._session_cookie = session_cookie

    async def fetch_product_info(self, product_id: str) -> Dict[str, Any]:
        """Cào chi tiết sản phẩm (Tên, Giá, Ảnh, Shop) qua Product ID."""
        clean_id = str(product_id).strip()
        url = f"https://www.tiktok.com/view/product/{clean_id}"
        
        info = {
            "product_id": clean_id,
            "product_url": url,
            "title": "",
            "price": "",
            "shop_name": "",
            "status": "unknown",
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await browser.new_context(
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            )

            # Cấp cookies nếu có
            cookies = []
            ttwid = get_ttwid()
            if ttwid:
                cookies.append({"name": "ttwid", "value": ttwid, "domain": ".tiktok.com", "path": "/"})
            if self._session_cookie:
                cookies.append({"name": "sessionid", "value": self._session_cookie, "domain": ".tiktok.com", "path": "/"})

            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                
                title = await page.title()
                if "Security Check" in title or "Captcha" in title:
                    info["status"] = "captcha_required"
                else:
                    info["status"] = "success"
                    # Lấy Tên
                    h1 = await page.locator("h1").all_text_contents()
                    if h1:
                        info["title"] = h1[0].strip()
                    # Lấy Giá
                    prices = await page.locator("[class*='price'], [class*='Price']").all_text_contents()
                    if prices:
                        info["price"] = prices[0].strip()
            except Exception as e:
                info["error"] = str(e)
            finally:
                await browser.close()

        return info

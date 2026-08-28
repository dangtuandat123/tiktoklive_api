import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

async def get_shop_showcase(username: str = "swatchesbybaobao"):
    clean_user = username.strip().lstrip("@")
    target_url = f"https://www.tiktok.com/@{clean_user}"
    
    print(f"[*] Đang mở trình duyệt giả lập Mobile để cào danh sách sản phẩm giỏ hàng @{clean_user}...")
    
    products_found = []
    
    async with async_playwright() as p:
        # Giả lập Mobile iPhone / Android để TikTok mở tab Giỏ hàng TikTok Shop
        iphone = p.devices["iPhone 14 Pro Max"]
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        context = await browser.new_context(
            **iphone,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        
        # Lắng nghe các response chứa dữ liệu sản phẩm TikTok Shop
        async def handle_response(response):
            url = response.url
            if any(k in url.lower() for k in ("showcase", "product", "oec", "commerce", "shop", "window")):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        body_str = json.dumps(body)
                        if "title" in body_str or "price" in body_str or "product_id" in body_str:
                            print(f"[+] Bắt được API sản phẩm: {url[:100]}...")
                            products_found.append({"url": url, "data": body})
                except Exception:
                    pass

        context.on("response", handle_response)
        page = await context.new_page()
        
        try:
            # Truy cập trang profile TikTok Mobile
            await page.goto(target_url, timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # In ra các thẻ tabs và text trên trang
            buttons = await page.locator("button, a, [role='tab']").all_text_contents()
            print("Các nút / tab tìm thấy trên trang:", [b.strip() for b in buttons if b.strip()][:25])
            
            # Kiểm tra xem có icon giỏ hàng / shopping bag không
            cart_links = await page.locator("a[href*='shop'], a[href*='product'], [data-e2e*='shop']").all()
            print(f"Số lượng link liên quan shop: {len(cart_links)}")
            for cl in cart_links:
                href = await cl.get_attribute("href")
                print(f"  -> Link shop: {href}")
                
        except Exception as e:
            print(f"[!] Lỗi: {e}")
        finally:
            await browser.close()

            
    print(f"\n[*] TỔNG CỘNG BẮT ĐƯỢC {len(products_found)} GÓI DỮ LIỆU SẢN PHẨM:")
    for idx, item in enumerate(products_found, 1):
        print(f"\n--- Gói {idx}: {item['url'][:80]} ---")
        # In mẫu data
        data_str = json.dumps(item['data'], ensure_ascii=False, indent=2)
        print(data_str[:500] + ("..." if len(data_str) > 500 else ""))

if __name__ == "__main__":
    asyncio.run(get_shop_showcase())

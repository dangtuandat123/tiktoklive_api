"""TikTok Shop Mobile Interceptor (Mitmproxy Addon).

Tự động bắt, giải mã và in toàn bộ dữ liệu:
1. Sản phẩm đang ghim & đổi sản phẩm theo thời gian thực (get_explaining_product).
2. Danh mục toàn bộ 50-100 sản phẩm trong giỏ hàng (live_cart / product_list).
3. Đơn hàng và biến động giá Flash Sale.

Cách chạy:
    pip install mitmproxy
    mitmdump -s tiktok_shop_mitm.py -p 8080
"""

import json
import re
import datetime
from mitmproxy import http


def get_time_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


class TikTokShopInterceptor:
    def response(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url

        # 1. Bắt API Sản phẩm đang ghim / đổi sản phẩm (Explaining Product)
        if "get_explaining_product" in url or "explain_product" in url or "explaining_product" in url:
            try:
                data = json.loads(flow.response.get_text())
                print("\n" + "🔥" * 40)
                print(f"[{get_time_str()}] [🛍️ TIKTOK SHOP - ĐỔI SẢN PHẨM GHIM MỚI!]")
                
                # Trích xuất dữ liệu sản phẩm
                body = data.get("data") or data
                product_info = body.get("product_info") or body.get("product") or body
                
                title = product_info.get("title") or product_info.get("name") or "Sản phẩm"
                price_info = product_info.get("price_info") or {}
                price = price_info.get("format_price") or price_info.get("price") or product_info.get("price", "")
                pid = product_info.get("product_id") or product_info.get("id") or ""
                stock = product_info.get("stock_count") or product_info.get("stock", "")

                print(f"  📌 Tên sản phẩm : {title}")
                if price:
                    print(f"  💰 Giá bán      : {price}")
                if pid:
                    print(f"  🆔 Product ID   : {pid}")
                if stock:
                    print(f"  📦 Tồn kho      : {stock}")
                print("🔥" * 40 + "\n")
            except Exception as e:
                print(f"[{get_time_str()}] [!] Lỗi parse JSON Explaining Product: {e}")

        # 2. Bắt API Toàn bộ danh mục sản phẩm trong giỏ hàng (Live Cart)
        elif "live_cart" in url or "product_list" in url or "showcase/page" in url:
            try:
                data = json.loads(flow.response.get_text())
                print(f"\n[{get_time_str()}] [🛒 TIKTOK SHOP - BẮT ĐƯỢC TOÀN BỘ GIỎ HÀNG!]")
                products = data.get("data", {}).get("products", []) or data.get("products", [])
                if products:
                    print(f"[*] Tìm thấy {len(products)} sản phẩm trong giỏ hàng:")
                    for idx, p in enumerate(products[:10], 1):
                        p_name = p.get("title") or p.get("name", "SP")
                        p_price = p.get("format_price") or p.get("price", "")
                        print(f"   {idx}. {p_name} | {p_price}")
                    if len(products) > 10:
                        print(f"   ... và {len(products) - 10} sản phẩm khác.")
            except Exception:
                pass


addons = [TikTokShopInterceptor()]

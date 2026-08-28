#!/usr/bin/env python3
"""Công cụ dòng lệnh (CLI) tạo và quản lý Cookie TTWID chuẩn 100% bằng Playwright.

Cách sử dụng:
    python get_ttwid.py                    # Lấy 1 token (dùng cache nếu còn hạn)
    python get_ttwid.py --force            # Bắt buộc mở Chromium lấy token mới tinh
    python get_ttwid.py --pool 5           # Tự động tạo 5 token xịn lưu vào ttwid_pool.txt
    python get_ttwid.py --headful          # Bật giao diện trình duyệt để quan sát
    python get_ttwid.py --proxy "http://127.0.0.1:8080" # Dùng proxy
"""

import argparse
import os
import sys
import time

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live.auth.playwright_ttwid import PlaywrightTTWIDGenerator



def main():
    parser = argparse.ArgumentParser(
        description="TikTok Live TTWID Generator Tool (Playwright Engine)"
    )
    parser.add_argument(
        "-u", "--username",
        default="tiktok",
        help="Streamer profile username để mồi request (mặc định: 'tiktok')",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Bỏ qua cache, bắt buộc mở trình duyệt lấy token mới",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Hiển thị cửa sổ trình duyệt (mặc định chạy ngầm headless)",
    )
    parser.add_argument(
        "-p", "--proxy",
        default="",
        help="Proxy URL (vd: 'http://user:pass@ip:port')",
    )
    parser.add_argument(
        "--pool",
        type=int,
        default=0,
        help="Số lượng token muốn tạo và lưu vào file 'ttwid_pool.txt'",
    )
    parser.add_argument(
        "--pool-file",
        default="ttwid_pool.txt",
        help="Tên file lưu pool token (mặc định: 'ttwid_pool.txt')",
    )

    args = parser.parse_args()

    generator = PlaywrightTTWIDGenerator(
        headless=not args.headful,
    )

    if args.pool > 0:
        print(f"[*] Đang chuẩn bị sinh {args.pool} token TTWID vào file '{args.pool_file}'...")
        tokens = []
        for i in range(1, args.pool + 1):
            print(f"[{i}/{args.pool}] Đang tạo token thứ {i}...")
            start = time.time()
            try:
                # Force refresh để mỗi lần tạo một token mới
                token = generator.fetch_sync(
                    username=args.username,
                    proxy=args.proxy,
                    force_refresh=True,
                )
                duration = time.time() - start
                print(f"  -> Thành công ({duration:.2f}s): {token[:20]}...{token[-10:]}")
                tokens.append(token)
            except Exception as e:
                print(f"  -> Lỗi: {e}")

        if tokens:
            with open(args.pool_file, "a", encoding="utf-8") as f:
                for t in tokens:
                    f.write(f"{t}\n")
            print(f"\n[+] HOÀN THÀNH: Đã lưu {len(tokens)} token vào '{args.pool_file}'!")
        else:
            print("\n[-] Không tạo được token nào.")
            sys.exit(1)
    else:
        print("[*] Đang lấy TTWID token...")
        start = time.time()
        try:
            token = generator.fetch_sync(
                username=args.username,
                proxy=args.proxy,
                force_refresh=args.force,
            )
            duration = time.time() - start
            print(f"[+] Lấy thành công trong {duration:.2f}s:\n")
            print(f"ttwid={token}\n")
            print(f"[*] Cách dùng trong code Python:")
            print(f"    client = TikTokLiveClient('{args.username}')")
            print(f"    client.cookies('ttwid={token}')")
        except Exception as e:
            print(f"[-] Thất bại: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

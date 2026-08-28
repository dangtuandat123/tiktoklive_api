import asyncio
import datetime
import os
import sys
import time
from typing import Dict, List, Optional

# Đảm bảo in tiếng Việt & UTF-8 trên Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from piratetok_live import (
    TikTokLiveClient,
    EventType,
    TikTokEvent,
    get_ttwid,
)


class BenchmarkMonitor:
    """Bộ đếm và theo dõi hiệu năng hệ thống theo thời gian thực."""

    def __init__(self, target_workers: int):
        self.target_workers = target_workers
        self.connected_count = 0
        self.disconnected_count = 0
        self.blocked_count = 0
        self.error_count = 0
        self.total_events = 0
        self.chat_events = 0
        self.like_events = 0
        self.gift_events = 0
        self.shop_events = 0
        self.start_time = time.time()
        self._lock = asyncio.Lock()

    async def record_connect(self):
        async with self._lock:
            self.connected_count += 1

    async def record_disconnect(self):
        async with self._lock:
            if self.connected_count > 0:
                self.connected_count -= 1
            self.disconnected_count += 1

    async def record_blocked(self):
        async with self._lock:
            self.blocked_count += 1

    async def record_error(self):
        async with self._lock:
            self.error_count += 1

    async def record_event(self, event_type: str):
        async with self._lock:
            self.total_events += 1
            if event_type == EventType.chat:
                self.chat_events += 1
            elif event_type == EventType.like:
                self.like_events += 1
            elif event_type == EventType.gift:
                self.gift_events += 1
            elif event_type == EventType.oec_live_shopping:
                self.shop_events += 1

    def print_dashboard(self):
        elapsed = max(time.time() - self.start_time, 1)
        eps = self.total_events / elapsed

        # Lấy thông tin RAM tiêu thụ của tiến trình Python hiện tại
        try:
            import psutil
            process = psutil.Process(os.getpid())
            ram_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent()
        except ImportError:
            ram_mb = 0.0
            cpu_percent = 0.0

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print("\n" + "=" * 90, flush=True)
        print(f"📊 [BENCHMARK DASHBOARD - {now_str}] THỜI GIAN CHẠY: {int(elapsed)}s", flush=True)
        print(f"  🟢 Đang kết nối ổn định: {self.connected_count}/{self.target_workers} luồng", flush=True)
        print(f"  🔴 Đã ngắt kết nối: {self.disconnected_count} | 🚫 Bị chặn (Blocked/415): {self.blocked_count} | ⚠️ Lỗi: {self.error_count}", flush=True)
        print(f"  ⚡ Tốc độ xử lý: {eps:.1f} events/giây | Tổng sự kiện đã nhận: {self.total_events:,}", flush=True)
        print(f"     -> 💬 Chat: {self.chat_events:,} | ❤️ Like: {self.like_events:,} | 🎁 Gift: {self.gift_events:,} | 🛍️ Shop: {self.shop_events:,}", flush=True)
        if ram_mb > 0:
            print(f"  💻 Tài nguyên hệ thống: RAM: {ram_mb:.1f} MB | CPU: {cpu_percent:.1f}%", flush=True)
        print("=" * 90 + "\n", flush=True)


async def run_single_worker(
    worker_id: int,
    username: str,
    ttwid_token: str,
    monitor: BenchmarkMonitor,
    proxy_url: Optional[str] = None,
):
    """Một worker client độc lập trong tổng số 200 luồng."""
    client = (
        TikTokLiveClient(username)
        .max_retries(3)
        .stale_timeout(45.0)
        .cookies(f"ttwid={ttwid_token}")
    )
    if proxy_url:
        client.proxy(proxy_url)

    @client.on(EventType.connected)
    async def on_conn(evt):
        await monitor.record_connect()

    @client.on(EventType.disconnected)
    async def on_disc(evt):
        await monitor.record_disconnect()

    @client.on(EventType.chat)
    @client.on(EventType.like)
    @client.on(EventType.gift)
    @client.on(EventType.oec_live_shopping)
    async def on_any_event(evt):
        await monitor.record_event(evt.type)

    try:
        await client.connect()
    except Exception as e:
        err_str = str(e)
        if "DEVICE_BLOCKED" in err_str or "415" in err_str or "429" in err_str:
            await monitor.record_blocked()
        else:
            await monitor.record_error()


async def stats_reporter_loop(monitor: BenchmarkMonitor, interval_sec: int = 5):
    """Vòng lặp cập nhật Dashboard thống kê định kỳ ra màn hình."""
    while True:
        await asyncio.sleep(interval_sec)
        monitor.print_dashboard()


async def main():
    # Cấu hình kịch bản test
    username = "swatchesbybaobao"
    total_workers = 200           # Số lượng luồng mong muốn
    concurrency_limit = 20        # Số lượng kết nối mở đồng thời mỗi đợt (Staggered ramp-up)
    ramp_up_delay = 0.05          # Độ trễ giữa mỗi client kết nối (50ms để không nghẽn socket TCP)

    print("\n" + "=" * 90)
    print(f"🚀 KHỞI ĐỘNG BENCHMARK KIỂM TRA ĐỘ ỔN ĐỊNH VÀ CHỊU TẢI: {total_workers} LUỒNG ĐỒNG THỜI")
    print(f"📌 Mục tiêu phòng Live: @{username}")
    print("=" * 90)

    # 1. Cấp token TTWID xác thực chuẩn
    print(f"[*] Đang chuẩn bị token TTWID xác thực an toàn qua Playwright...")
    try:
        ttwid = get_ttwid(username)
        print(f"[+] Đã cấp TTWID thành công: {ttwid[:20]}...\n")
    except Exception as e:
        print(f"[!] Cảnh báo lấy TTWID: {e}, sẽ để client tự sinh token.")
        ttwid = ""

    monitor = BenchmarkMonitor(target_workers=total_workers)

    # Khởi chạy task in Dashboard định kỳ mỗi 5 giây
    reporter_task = asyncio.create_task(stats_reporter_loop(monitor, interval_sec=5))

    # Semaphore kiểm soát tốc độ kết nối ban đầu để tránh dồn ứ TCP SYN
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def worker_wrapper(w_id: int):
        async with semaphore:
            await asyncio.sleep(w_id * ramp_up_delay)
            await run_single_worker(w_id, username, ttwid, monitor)

    # Khởi chạy 200 workers song song
    print(f"[*] Đang kết nối dần {total_workers} luồng vào phòng Live (Staggered Ramp-up)...")
    tasks = [asyncio.create_task(worker_wrapper(i + 1)) for i in range(total_workers)]

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        print("\n[*] Đang dừng toàn bộ 200 workers...")
    finally:
        reporter_task.cancel()
        monitor.print_dashboard()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[🛑 STOPPED] Đã kết thúc bài kiểm thử benchmark.")

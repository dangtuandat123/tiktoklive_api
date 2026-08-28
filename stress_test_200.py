import asyncio
import datetime
import os
import sys
sys.path.insert(0, ".")
import time
from typing import Dict, List, Optional, Any

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


def get_time_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


class WorkerState:
    CONNECTING = "🟡 CONNECTING"
    ONLINE = "🟢 ONLINE"
    RECONNECTING = "🔄 RECONNECTING"
    DISCONNECTED = "🔌 DISCONNECTED"
    BLOCKED = "🚫 BLOCKED"
    ERROR = "⚠️ ERROR"


class BenchmarkMonitor:
    """Bộ giám sát chi tiết từng Worker và toàn bộ hệ thống theo thời gian thực."""

    def __init__(self, target_workers: int):
        self.target_workers = target_workers
        self.workers: Dict[int, Dict[str, Any]] = {
            i: {
                "status": WorkerState.CONNECTING,
                "events": 0,
                "last_error": "",
                "connected_at": 0.0,
            }
            for i in range(1, target_workers + 1)
        }
        self.total_events = 0
        self.chat_events = 0
        self.like_events = 0
        self.gift_events = 0
        self.shop_events = 0
        self.start_time = time.time()
        self._lock = asyncio.Lock()
        self.recent_incidents: List[str] = []

    async def record_connect(self, worker_id: int):
        async with self._lock:
            self.workers[worker_id]["status"] = WorkerState.ONLINE
            self.workers[worker_id]["connected_at"] = time.time()
            self.workers[worker_id]["last_error"] = ""

    async def record_reconnecting(self, worker_id: int, attempt: int, delay: float):
        async with self._lock:
            self.workers[worker_id]["status"] = WorkerState.RECONNECTING
            msg = f"[{get_time_str()}] 🔄 [Worker #{worker_id:03d}] Đang kết nối lại lần {attempt} (chờ {delay}s)..."
            self.recent_incidents.append(msg)
            if len(self.recent_incidents) > 6:
                self.recent_incidents.pop(0)

    async def record_disconnect(self, worker_id: int, reason: str = "Closed"):
        async with self._lock:
            self.workers[worker_id]["status"] = WorkerState.DISCONNECTED
            self.workers[worker_id]["last_error"] = reason
            msg = f"[{get_time_str()}] 🔌 [Worker #{worker_id:03d}] Đã ngắt kết nối: {reason}"
            self.recent_incidents.append(msg)
            if len(self.recent_incidents) > 6:
                self.recent_incidents.pop(0)

    async def record_blocked(self, worker_id: int, reason: str):
        async with self._lock:
            self.workers[worker_id]["status"] = WorkerState.BLOCKED
            self.workers[worker_id]["last_error"] = reason
            msg = f"[{get_time_str()}] 🚫 [Worker #{worker_id:03d}] PHÁT HIỆN BỊ CHẶN: {reason}"
            print(f"\n{msg}", flush=True)
            self.recent_incidents.append(msg)
            if len(self.recent_incidents) > 6:
                self.recent_incidents.pop(0)

    async def record_error(self, worker_id: int, error_msg: str):
        async with self._lock:
            self.workers[worker_id]["status"] = WorkerState.ERROR
            self.workers[worker_id]["last_error"] = error_msg
            msg = f"[{get_time_str()}] ⚠️ [Worker #{worker_id:03d}] LỖI: {error_msg}"
            self.recent_incidents.append(msg)
            if len(self.recent_incidents) > 6:
                self.recent_incidents.pop(0)

    async def record_event(self, worker_id: int, event_type: str):
        async with self._lock:
            self.total_events += 1
            self.workers[worker_id]["events"] += 1
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

        # Thống kê số lượng từng trạng thái
        online_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.ONLINE]
        blocked_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.BLOCKED]
        reconn_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.RECONNECTING]
        disc_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.DISCONNECTED]
        err_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.ERROR]
        conn_list = [wid for wid, w in self.workers.items() if w["status"] == WorkerState.CONNECTING]

        # Đo RAM & CPU
        try:
            import psutil
            process = psutil.Process(os.getpid())
            ram_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent()
        except ImportError:
            ram_mb = 0.0
            cpu_percent = 0.0

        now_str = get_time_str()
        print("\n" + "=" * 95, flush=True)
        print(f"📊 [BENCHMARK DASHBOARD - {now_str}] THỜI GIAN CHẠY: {int(elapsed)}s", flush=True)
        print(f"  🟢 ONLINE HOẠT ĐỘNG: {len(online_list)}/{self.target_workers} luồng", flush=True)
        print(f"  🟡 Đang kết nối: {len(conn_list)} | 🔄 Đang reconnect: {len(reconn_list)}", flush=True)
        print(f"  🚫 BỊ CHẶN (Blocked/415/429): {len(blocked_list)} luồng | 🔌 Đã ngắt: {len(disc_list)} | ⚠️ Lỗi khác: {len(err_list)}", flush=True)
        print(f"  ⚡ Tốc độ bắt gói tin: {eps:.1f} events/giây | Tổng sự kiện đã nhận: {self.total_events:,}", flush=True)
        print(f"     -> 💬 Chat: {self.chat_events:,} | ❤️ Like: {self.like_events:,} | 🎁 Gift: {self.gift_events:,} | 🛍️ Shop: {self.shop_events:,}", flush=True)
        if ram_mb > 0:
            print(f"  💻 Tài nguyên hệ thống: RAM: {ram_mb:.1f} MB | CPU: {cpu_percent:.1f}%", flush=True)

        # In chi tiết danh sách các Worker bị chặn hoặc gặp sự cố
        if blocked_list:
            print("\n  🚨 DANH SÁCH WORKER BỊ CHẶN:", flush=True)
            for wid in blocked_list[:10]:
                err = self.workers[wid]["last_error"]
                print(f"     * Worker #{wid:03d} -> Nguyên nhân: {err}", flush=True)
            if len(blocked_list) > 10:
                print(f"     * ... và {len(blocked_list) - 10} worker khác bị chặn.", flush=True)

        if err_list:
            print("\n  ⚠️ DANH SÁCH WORKER BỊ LỖI:", flush=True)
            for wid in err_list[:5]:
                err = self.workers[wid]["last_error"]
                print(f"     * Worker #{wid:03d} -> Lỗi: {err}", flush=True)

        # In nhật ký sự cố gần nhất
        if self.recent_incidents:
            print("\n  📜 NHẬT KÝ SỰ CỐ GẦN NHẤT:", flush=True)
            for inc in self.recent_incidents[-4:]:
                print(f"     {inc}", flush=True)

        print("=" * 95 + "\n", flush=True)


async def run_single_worker(
    worker_id: int,
    username: str,
    ttwid_token: str,
    room_id: str,
    monitor: BenchmarkMonitor,
    proxy_url: Optional[str] = None,
):
    """Một worker client độc lập trong tổng số 200 luồng."""
    client = (
        TikTokLiveClient(username)
        .room_id(room_id)
        .max_retries(3)
        .stale_timeout(45.0)
        .cookies(f"ttwid={ttwid_token}")
    )
    if proxy_url:
        client.proxy(proxy_url)

    @client.on(EventType.connected)
    async def on_conn(evt):
        await monitor.record_connect(worker_id)

    @client.on(EventType.reconnecting)
    async def on_reconn(evt):
        d = evt.data or {}
        await monitor.record_reconnecting(worker_id, d.get("attempt", 1), d.get("delay", 2.0))

    @client.on(EventType.disconnected)
    async def on_disc(evt):
        await monitor.record_disconnect(worker_id, "Phiên WSS kết thúc")

    @client.on(EventType.chat)
    @client.on(EventType.like)
    @client.on(EventType.gift)
    @client.on(EventType.oec_live_shopping)
    async def on_any_event(evt):
        await monitor.record_event(worker_id, evt.type)

    try:
        await client.connect()
    except Exception as e:
        err_str = str(e)
        # Phân loại chính xác nguyên nhân lỗi
        if "DEVICE_BLOCKED" in err_str or "415" in err_str:
            await monitor.record_blocked(worker_id, f"DEVICE_BLOCKED (HTTP 415) - Cắm cờ thiết bị / TTWID")
        elif "429" in err_str or "Too Many Requests" in err_str:
            await monitor.record_blocked(worker_id, f"RATE_LIMITED (HTTP 429) - Quá tải số lượng kết nối trên 1 IP")
        elif "403" in err_str or "Forbidden" in err_str:
            await monitor.record_blocked(worker_id, f"FORBIDDEN (HTTP 403) - IP bị tường lửa TikTok chặn")
        elif "HostNotOnlineError" in err_str:
            await monitor.record_error(worker_id, f"Streamer hiện không phát Live")
        elif "Timeout" in err_str:
            await monitor.record_error(worker_id, f"Timeout kết nối (Mạng nghẽn)")
        else:
            await monitor.record_error(worker_id, f"{type(e).__name__}: {err_str[:60]}")


async def stats_reporter_loop(monitor: BenchmarkMonitor, interval_sec: int = 5):
    """Vòng lặp cập nhật Dashboard thống kê định kỳ ra màn hình."""
    while True:
        await asyncio.sleep(interval_sec)
        monitor.print_dashboard()


async def main():
    username = "swatchesbybaobao"
    total_workers = 200           # Số lượng luồng mong muốn (200 luồng)
    ramp_up_delay = 0.05          # Khởi động mỗi luồng cách nhau 50ms (10 giây để bật đủ 200 luồng)

    print("\n" + "=" * 95)
    print(f"🚀 KHỞI ĐỘNG BENCHMARK KIỂM TRA ĐỘ ỔN ĐỊNH VÀ CHỊU TẢI: {total_workers} LUỒNG ĐỒNG THỜI")
    print(f"📌 Mục tiêu phòng Live: @{username}")
    print(f"🔍 Cơ chế nhận diện: Định danh Worker ID, Bắt mã lỗi (415, 429, 403) và Nhật ký thời gian thực")
    print("=" * 95)

    # 1. Cấp token TTWID xác thực chuẩn
    print(f"[*] Đang chuẩn bị token TTWID xác thực an toàn qua Playwright...")
    try:
        ttwid = get_ttwid(username)
        print(f"[+] Đã cấp TTWID thành công: {ttwid[:20]}...")
    except Exception as e:
        print(f"[!] Cảnh báo lấy TTWID: {e}, sẽ để client tự sinh token.")
        ttwid = ""

    # 2. Khám phá Room ID một lần duy nhất dùng chung cho 200 luồng
    print(f"[*] Đang kiểm tra phòng Live của @{username}...")
    try:
        room_res = TikTokLiveClient.check_online(username)
        room_id = room_res.room_id
        print(f"[+] Tìm thấy phòng Live ID: {room_id}\n")
    except Exception as e:
        print(f"[!] Không thể lấy Room ID ({e}), sẽ để từng worker tự tìm.")
        room_id = ""

    monitor = BenchmarkMonitor(target_workers=total_workers)

    # Khởi chạy task in Dashboard định kỳ mỗi 5 giây
    reporter_task = asyncio.create_task(stats_reporter_loop(monitor, interval_sec=5))

    # Khởi chạy 200 workers song song (Khởi động tuần tự 50ms/worker không bị nghẽn)
    print(f"[*] Đang kết nối dần {total_workers} luồng vào phòng Live (Staggered Ramp-up 50ms/worker)...")
    tasks = []
    for i in range(total_workers):
        w_id = i + 1
        tasks.append(asyncio.create_task(run_single_worker(w_id, username, ttwid, room_id, monitor)))
        await asyncio.sleep(ramp_up_delay)

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

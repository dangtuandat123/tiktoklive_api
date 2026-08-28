# PirateTok Live (Python Engine) — Kiến Trúc & Sổ Tay Kỹ Thuật Bảo Trì

> **Tài liệu đặc tả kỹ thuật, thuật toán và hướng dẫn bảo trì toàn diện 100% cho thư viện `piratetok_live`.**  
> Thư viện cung cấp khả năng kết nối bất đồng bộ (`asyncio`) thời gian thực tới máy chủ **TikTok Live Webcast WebSocket (WSS)**, tự động giải mã các gói tin nhị phân **Protocol Buffers (Protobuf)**, xử lý nén **Gzip**, vượt cơ chế chống bot **JA3/JA4 TLS Fingerprint**, tự động phân luồng sự kiện và điều phối kết nối bền bỉ.

---

## MỤC LỤC

1. [Tổng Quan Kiến Trúc Hệ Thống](#1-tổng-quan-kiến-trúc-hệ-thống)
2. [Luồng Thuật Toán Hoạt Động End-to-End](#2-luồng-thuật-toán-hoạt-động-end-to-end)
3. [Đặc Tả Chi Tiết Từng Module, File, Lớp & Hàm](#3-đặc-tả-chi-tiết-từng-module-file-lớp--hàm)
   - [3.1. `piratetok_live/client.py` (Orchestrator trung tâm)](#31-piratetok_liveclientpy)
   - [3.2. `piratetok_live/auth/ttwid.py` (Bypass Anti-Bot & Mint TTWID)](#32-piratetok_liveauthttwidpy)
   - [3.3. `piratetok_live/connection/` (Giao thức kết nối WSS & Xử lý Frame)](#33-piratetok_liveconnection)
   - [3.4. `piratetok_live/events/` (Định tuyến & Giải mã Protobuf)](#34-piratetok_liveevents)
   - [3.5. `piratetok_live/helpers/` (Các thuật toán toán học & Cache dữ liệu)](#35-piratetok_livehelpers)
   - [3.6. `piratetok_live/http/` (Giao tiếp HTTP, Scraper & Device Helpers)](#36-piratetok_livehttp)
   - [3.7. `piratetok_live/proto/` (Schemas Protocol Buffers)](#37-piratetok_liveproto)
   - [3.8. `piratetok_live/errors.py` (Hệ thống ngoại lệ)](#38-piratetok_liveerrorspy)
4. [Bảng Ma Trận Đầy Đủ 72 Sự Kiện (Event Reference Matrix)](#4-bảng-ma-trận-đầy-đủ-72-sự-kiện-event-reference-matrix)
5. [Cấu Trúc Các Model Dữ Liệu (Data Models)](#5-cấu-trúc-các-model-dữ-liệu-data-models)
6. [Sổ Tay Hướng Dẫn Bảo Trì & Xử Lý Sự Cố (Troubleshooting Manual)](#6-sổ-tay-hướng-dẫn-bảo-trì--xử-lý-sự-cố)
7. [Các Kịch Bản Sử Dụng Mẫu (Usage Examples)](#7-các-kịch-bản-sử-dụng-mẫu-usage-examples)

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG

Hệ thống được thiết kế theo mô hình phân tầng hướng sự kiện (**Event-Driven Layered Architecture**):

```
+-----------------------------------------------------------------------------------+
|                            APPLICATION / CONSUMER LAYER                           |
|                      (example.py, FastAPI, Webhook Worker, ...)                   |
+-----------------------------------------+-----------------------------------------+
                                          | @client.on(EventType.chat, ...)
+-----------------------------------------v-----------------------------------------+
|                        CONTROLLER LAYER: TikTokLiveClient                         |
|     (Quản lý vòng đời kết nối, cấu hình tham số, Exponential Backoff Reconnect)   |
+--------------------+--------------------+--------------------+--------------------+
                     |                    |                    |
+--------------------v----+ +-------------v----------+ +-------v--------------------+
|    HTTP & AUTH LAYER    | |    CONNECTION LAYER    | |    DECODING & ROUTING      |
|                         | |                        | |                            |
| * check_online()        | | * build_wss_url()      | | * decompress_if_gzipped()  |
| * fetch_room_info()     | | * Frame Packets (HB,   | | * WebcastPushFrame Parser  |
| * fetch_ttwid() (cffi)  | |   EnterRoom, ACK)      | | * betterproto Message Map  |
| * scrape_profile()      | | * connect_wss()        | | * Sub-routing (Join, Share)|
| * SIGI JSON Extractor   | | * Heartbeat Loop       | | * Gift enrichments         |
+-------------------------+ +------------------------+ +----------------------------+
                     |                    |                    |
+--------------------v--------------------v--------------------v--------------------+
|                         HELPER & DATA INTEGRITY LAYER                             |
|                                                                                   |
| * GiftStreakTracker (Tính delta quà combo từ repeat_count luỹ kế)                 |
| * LikeAccumulator (Chuẩn hóa số like đơn điệu từ các shard bất đồng bộ)          |
| * ProfileCache (Positive / Negative caching với Thread Lock bảo vệ)               |
+-----------------------------------------------------------------------------------+
```

---

## 2. LUỒNG THUẬT TOÁN HOẠT ĐỘNG END-TO-END

```mermaid
sequenceDiagram
    autonumber
    actor App as Application Code
    participant Client as TikTokLiveClient
    participant HTTP as HTTP API / Auth
    participant WSS as WebSocket Client
    participant Router as Event Router
    participant Helper as Helpers (Streak/Like)

    App->>Client: client = TikTokLiveClient("username")
    App->>Client: await client.connect()
    
    rect rgb(240, 245, 255)
    Note over Client,HTTP: Giai đoạn 1 & 2: Xác thực & Khám phá phòng Live
    Client->>HTTP: check_online(username) -> GET /api-live/user/room
    HTTP-->>Client: Trả về room_id (hoặc raise HostNotOnlineError / UserNotFoundError)
    Client->>HTTP: fetch_ttwid() qua curl_cffi (Chrome TLS Impersonation)
    HTTP-->>Client: Cookie ttwid mới (Bypass JA3/JA4 Edge Filter)
    end

    rect rgb(245, 255, 245)
    Note over Client,WSS: Giai đoạn 3 & 4: Khởi tạo WebSocket Handshake
    Client->>WSS: build_wss_url() -> wss://webcast-ws.tiktok.com/...
    Client->>WSS: connect_wss(headers={'Cookie': 'ttwid=...', 'User-Agent': ...})
    WSS->>WSS: Gửi PushFrame: Heartbeat (payload_type="hb")
    WSS->>WSS: Gửi PushFrame: EnterRoom (payload_type="im_enter_room")
    WSS->>WSS: Khởi chạy Task _heartbeat_loop (chu kỳ 10 giây/lần)
    end

    rect rgb(255, 250, 240)
    Note over WSS,Helper: Giai đoạn 5 & 6: Xử lý Frame nhị phân & Giải mã Protobuf
    loop Nhận Stream từ WebSocket
        WSS->>WSS: Nhận binary frame (WebcastPushFrame)
        alt Frame là Gzip (Magic bytes 0x1F 0x8B)
            WSS->>WSS: gzip.decompress(payload)
        end
        WSS->>WSS: Parse WebcastResponse
        opt response.needs_ack == True
            WSS->>WSS: Gửi phản hồi ACK kèm log_id
        end
        loop Mỗi Message trong WebcastResponse.messages
            WSS->>Router: decode(msg.method, msg.payload, room_id)
            Router->>Router: Tra cứu Protobuf Class trong _PROTO_CLASSES
            Router->>Router: msg.parse(payload) -> msg.to_dict()
            Router->>Router: Sub-routing: Social->(Follow/Share), Member->Join, Control->LiveEnded
            Router-->>Client: Trả về danh sách [TikTokEvent]
            opt Dùng Helper
                Client->>Helper: GiftStreakTracker.process() / LikeAccumulator.process()
            end
            Client->>App: Kích hoạt callback listener @client.on(...)
        end
    end
    end

    rect rgb(255, 240, 240)
    Note over Client,WSS: Giai đoạn 7: Phục hồi khi đứt kết nối / Bị chặn
    alt Gặp lỗi Handshake DEVICE_BLOCKED (HTTP 415 / Handshake-Msg)
        WSS-->>Client: Raise DeviceBlockedError
        Client->>Client: Reset ttwid, đổi User-Agent ngẫu nhiên, delay 2s
        Client->>Client: Reconnect vòng lặp mới
    else Mất mạng / Timeout
        Client->>Client: Exponential Backoff (2^attempt giây, tối đa 30s)
        Client->>Client: Reconnect (tối đa max_retries)
    end
    end
```

---

## 3. ĐẶC TẢ CHI TIẾT TỪNG MODULE, FILE, LỚP & HÀM

### 3.1. `piratetok_live/client.py`

Bộ điều phối trung tâm triển khai mẫu thiết kế **Fluent Builder** & **Orchestrator**.

#### Lớp `TikTokLiveClient(username: str)`

*   **Khởi tạo (`__init__`)**:
    *   `_username`: Tên định danh streamer.
    *   `_cdn_host`: Mặc định `"webcast-ws.tiktok.com"`.
    *   `_timeout`: `10.0` giây (HTTP timeout).
    *   `_max_retries`: `5` lần thử lại.
    *   `_stale_timeout`: `60.0` giây (ngắt kết nối nếu không có gói tin nào gửi tới trong 60s).
    *   `_compress`: `True` (bật nén Gzip WSS).
    *   `_listeners`: `Dict[str, List[Callable]]` (bảng lưu trữ callback sự kiện).
*   **Các phương thức cấu hình (Fluent API)**:
    *   `cdn(host: str) -> self`: Gán host CDN tùy chỉnh.
    *   `cdn_eu() -> self`: Chuyển sang CDN Châu Âu (`"webcast-ws.eu.tiktok.com"`).
    *   `cdn_us() -> self`: Chuyển sang CDN Bắc Mỹ (`"webcast-ws.us.tiktok.com"`).
    *   `timeout(seconds: float) -> self`: Thiết lập timeout cho các request HTTP.
    *   `max_retries(n: int) -> self`: Thiết lập số lần reconnect tối đa.
    *   `stale_timeout(seconds: float) -> self`: Thiết lập thời gian chờ tối đa khi WebSocket bị im lặng.
    *   `proxy(url: str) -> self`: Thiết lập Proxy (hỗ trợ HTTP, HTTPS, SOCKS5).
    *   `user_agent(ua: str) -> self`: Gán User-Agent cố định (nếu không gán, hệ thống tự động xoay vòng ngẫu nhiên để chống chặn thiết bị).
    *   `language(lang: str) -> self`: Ghi đè mã ngôn ngữ hệ thống (vd: `"vi"`, `"en"`).
    *   `region(reg: str) -> self`: Ghi đè mã quốc gia (vd: `"VN"`, `"US"`).
    *   `compress(enabled: bool) -> self`: Bật/tắt nén Gzip trên WebSocket.
    *   `cookies(cookies: str) -> self`: Truyền cookie phiên người dùng hoặc cookie phòng 18+.
*   **Các phương thức quản lý sự kiện & kết nối**:
    *   `on(event_type: str) -> Callable`: Decorator đăng ký hàm lắng nghe sự kiện (`EventType.*` hoặc `*` cho toàn bộ sự kiện).
    *   `_emit(event: TikTokEvent)`: Phát sự kiện tới các listener tương ứng và listener toàn cục `*`.
    *   `_extract_ttwid() -> Optional[str]`: Phân tích chuỗi cookies để trích xuất `ttwid` người dùng truyền vào.
    *   `async connect() -> str`: Vòng lặp kết nối chính (quản lý auto-reconnect, xoay vòng TTWID khi gặp `DeviceBlockedError`, Exponential Backoff). Trả về `room_id`.
    *   `run() -> str`: Phương thức đồng bộ bao bọc `asyncio.run(self.connect())`.
    *   `disconnect() -> None`: Đặt cờ dừng `_stop.set()` để đóng WebSocket sạch sẽ.
*   **Các phương thức tĩnh (Static Helper Methods)**:
    *   `check_online(username: str, timeout: float = 10.0) -> RoomIdResult`: Kiểm tra trạng thái livestream.
    *   `fetch_room_info(room_id: str, timeout: float = 10.0, cookies: str = "") -> RoomInfo`: Lấy thông tin phòng và link luồng RTMP/FLV.

---

### 3.2. `piratetok_live/auth/` (Quản lý Cookie Xác Thực TTWID)

#### A. `piratetok_live/auth/ttwid.py` (Cơ chế Fast TLS Impersonation)
*   **Cơ chế kỹ thuật**: Sử dụng `curl_cffi` giả lập Chrome TLS Fingerprint để gửi request GET nhẹ (~5MB RAM) và lấy `ttwid` trong 200 - 400ms.
*   **Hàm chính**: `fetch_ttwid(timeout, proxy, user_agent, username) -> str`.

#### B. `piratetok_live/auth/playwright_ttwid.py` (Cơ chế Headless Chromium Chuẩn 100%)
*   **Đặc điểm đóng gói**: Thiết kế Zero-Coupling, chạy độc lập, tự động fallback đa kênh trình duyệt:
    1. *Kênh 1:* Bundled Playwright Chromium (`chromium.launch`).
    2. *Kênh 2:* Google Chrome hệ thống (`channel="chrome"`).
    3. *Kênh 3:* Microsoft Edge hệ thống (`channel="msedge"`).
*   **Tính năng Stealth & Tối ưu hóa**:
    *   Xóa dấu vết tự động hóa: Tiêm `_STEALTH_JS` xóa `navigator.webdriver`, bổ sung `window.chrome`, giả lập danh sách plugin và ngôn ngữ.
    *   **Resource Blocker**: Chặn tải toàn bộ `image`, `media`, `font`, `stylesheet` giúp rút ngắn thời gian lấy cookie xuống chỉ còn **1 - 2 giây** và giảm 98% dung lượng mạng.
    *   **Smart Cache Manager**: Tự động lưu token vào `.ttwid_cache.json` với TTL 72 giờ (trả về tức thì **0ms** trong các lần gọi sau).
    *   **Dual Sync/Async API**: Cung cấp cả `fetch_async()` và `fetch_sync()` (tự điều phối luồng qua `ThreadPoolExecutor` an toàn khi chạy trong event loop).
*   **Lớp chính**: `PlaywrightTTWIDGenerator(headless=True, timeout_ms=15000, cache_file=".ttwid_cache.json", cache_ttl_hours=72.0)`
*   **Hàm tiện ích**: `get_ttwid(username, proxy, force_refresh, headless) -> str`, `get_ttwid_async(...) -> str`.

#### C. Công cụ dòng lệnh CLI `get_ttwid.py`
Công cụ chạy độc lập để test hoặc tạo pool token:
```bash
python get_ttwid.py                # Lấy 1 token (dùng cache nếu còn hạn)
python get_ttwid.py --force        # Bắt buộc mở Chromium sinh token mới
python get_ttwid.py --pool 5       # Tạo 5 token xịn lưu vào ttwid_pool.txt
python get_ttwid.py --headful      # Mở cửa sổ trình duyệt trực quan
python get_ttwid.py --proxy "..."  # Dùng proxy
```


---

### 3.3. `piratetok_live/connection/`

Quản lý chi tiết từng byte truyền qua kết nối WebSocket WSS.

#### A. `piratetok_live/connection/url.py`
*   `build_wss_url(cdn_host: str, room_id: str, language: str = "en", region: str = "US", compress: bool = True) -> str`:
    *   Tạo URL WebSocket đầy đủ tham số: `wss://{cdn_host}/webcast/im/ws_proxy/ws_reuse_supplement/?{query_string}`
    *   Các query parameters:
        *   `version_code=180800`, `update_version_code=2.0.0`: Phiên bản client Webcast.
        *   `aid=1988`, `live_id=12`: Định danh ứng dụng web TikTok Live.
        *   `device_platform=web`, `app_name=tiktok_web`, `browser_platform=Linux x86_64`.
        *   `compress=gzip` (hoặc rỗng nếu tắt nén).
        *   `resp_content_type=protobuf`: Định dạng dữ liệu nhị phân trả về.
        *   `heartbeat_duration=10000`: Yêu cầu chu kỳ gửi nhịp tim 10.000ms.
        *   `history_comment_count=6`: Tải 6 bình luận gần nhất trước khi vào phòng.
        *   `last_rtt`: Mô phỏng độ trễ mạng ngẫu nhiên `100.xxx ms`.
        *   `tz_name`: Tên múi giờ của hệ thống (vd: `"Asia/Ho_Chi_Minh"`).

#### B. `piratetok_live/connection/frames.py`
*   `build_heartbeat(room_id: str) -> bytes`: Đóng gói `HeartbeatMessage` vào `WebcastPushFrame(payload_encoding="pb", payload_type="hb")`.
*   `build_enter_room(room_id: str) -> bytes`: Đóng gói `WebcastImEnterRoomMessage` vào `WebcastPushFrame(payload_type="im_enter_room")`.
*   `build_ack(log_id: int, internal_ext: bytes) -> bytes`: Tạo gói tin xác nhận cho server: `WebcastPushFrame(payload_type="ack", log_id=log_id, payload=internal_ext)`.
*   `decompress_if_gzipped(data: bytes) -> bytes`: Kiểm tra 2 byte đầu `0x1F 0x8B`. Nếu đúng định dạng Gzip thì giải nén `gzip.decompress(data)`.

#### C. `piratetok_live/connection/wss.py`
*   `connect_wss(...)`:
    *   Mở phiên kết nối WebSocket bất đồng bộ qua `websockets.asyncio.client.connect`.
    *   Gửi liên tiếp 2 gói tin khởi tạo: `build_heartbeat()` và `build_enter_room()`.
    *   Khởi chạy background task `_heartbeat_loop()` (10s/lần).
    *   Đọc luồng dữ liệu liên tục với cơ chế phát hiện treo: `asyncio.wait_for(ws.recv(), timeout=stale_timeout)`.
*   `_is_device_blocked(err: ws_exc.InvalidStatusCode) -> bool`: Bắt mã trạng thái HTTP `415` hoặc header `Handshake-Msg: DEVICE_BLOCKED`.
*   `_heartbeat_loop(ws, room_id, stop_event)`: Vòng lặp gửi heartbeat định kỳ 10 giây.
*   `_process_frame(raw, ws, room_id, on_event)`:
    *   Parse gói tin `WebcastPushFrame`.
    *   Nếu `payload_type == "msg"`: Giải nén Gzip, parse `WebcastResponse`.
    *   Nếu `response.needs_ack == True`: Lập tức gửi gói `build_ack()`.
    *   Chuyển từng payload con sang `router.decode()` và gửi sự kiện tới callback.

---

### 3.4. `piratetok_live/events/`

Định nghĩa và điều phối giải mã Protobuf thành các đối tượng sự kiện.

#### A. `piratetok_live/events/types.py`
*   `EventType`: Chứa toàn bộ các hằng số tên sự kiện (vd: `connected`, `chat`, `gift`, `like`, `member`, `social`, `follow`, `share`, `join`, `live_ended`, `oec_live_shopping`, `privilege_advance`,...).
*   `ProductInfo`: Data Model chứa thông tin bóc tách hoàn chỉnh của sản phẩm TikTok Shop (`product_id`, `title`, `url`, `image`, `images`, `seller`, `sold_count`).
*   `TikTokEvent(NamedTuple)`:
    *   `type: str`: Tên loại sự kiện.
    *   `data: Any`: Dữ liệu sự kiện đã được chuyển sang kiểu `dict` Python.
    *   `room_id: str`: ID phòng livestream đang phát.
    *   **Các thuộc tính Ergonomic có sẵn**:
        *   `evt.product_id`: Lấy mã ID định danh duy nhất của sản phẩm TikTok Shop.
        *   `evt.product_url`: Đường dẫn link mua hàng TikTok Shop chuẩn SEO không bị Captcha.
        *   `evt.canonical_product_info(region="vn") -> ProductInfo`: Tự động trích xuất Tên sản phẩm tiếng Việt gốc, Ảnh bìa Thumbnail #1 HD, Bộ sưu tập ảnh gallery, Tên gian hàng và Lượt bán.
        *   `evt.viewer_count`, `evt.total_users`: Số người đang xem trực tiếp và tổng lượt xem.
        *   `evt.like_count`, `evt.total_likes`: Số lượt thả tim trong sự kiện và tổng like phòng.
        *   `evt.is_host`, `evt.is_mod`, `evt.is_sub`, `evt.is_fan`, `evt.fans_club_name`, `evt.fans_club_level`: Quyền hạn và huy hiệu người dùng.


#### B. `piratetok_live/events/router.py`
*   `_METHOD_MAP: Dict[str, str]`: Bảng tra cứu ánh xạ 64 tên Webcast method sang tên `EventType`.
*   `_PROTO_CLASSES: Dict[str, Type[betterproto.Message]]`: Registry tự động phát hiện và đăng ký tất cả các class `betterproto.Message` trong `proto.schema` và `proto.messages`.
*   `decode(method: str, payload: bytes, room_id: str = "") -> List[TikTokEvent]`:
    *   Tra cứu lớp Protobuf trong `_PROTO_CLASSES` và thực hiện `proto_cls().parse(payload).to_dict()`.
    *   **Enrichment cho Gift**: Tự động tính toán và bổ sung:
        *   `data["is_combo"] = msg.is_combo_gift()`
        *   `data["is_streak_over"] = msg.is_streak_over()`
        *   `data["diamond_total"] = msg.diamond_total()`
    *   **Sub-Routing Logic**:
        *   `WebcastSocialMessage`: `action == 1` -> Bắn thêm sự kiện `EventType.follow`; `2 <= action <= 5` -> Bắn thêm sự kiện `EventType.share`.
        *   `WebcastMemberMessage`: `action == 1` -> Bắn thêm sự kiện `EventType.join`.
        *   `WebcastControlMessage`: `action == 3` -> Bắn thêm sự kiện `EventType.live_ended`.

---

### 3.5. `piratetok_live/helpers/`

Các thuật toán tính toán và quản lý bộ nhớ đệm nâng cao.

#### A. `piratetok_live/helpers/gift_streak.py` (`GiftStreakTracker`)
*   **Vấn đề**: Khi khán giả tặng quà combo, TikTok gửi liên tiếp các sự kiện với trường `repeat_count` là số **lũy kế** (ví dụ: 1 -> 5 -> 15 -> 30). Nếu cộng dồn trực tiếp, tổng quà sẽ bị tính sai thành `1 + 5 + 15 + 30 = 51` thay vì `30`.
*   **Giải thuật**:
    *   Lưu trữ trạng thái theo `group_id`: `_streaks[group_id] = (repeat_count_cũ, timestamp)`.
    *   Tính delta quà mới nhận: `delta = max(repeat_count - prev_count, 0)`.
    *   Tính delta kim cương: `event_diamond_count = diamond_per_gift * delta`.
    *   Khi `repeat_end == 1`: Xóa `group_id` khỏi bộ nhớ.
    *   Hàm `_evict_stale(now)`: Tự động dọn dẹp các streak quá hạn 60 giây.
*   **Dữ liệu trả về**: Đối tượng [`GiftStreakEvent`](#5-cấu-trúc-các-model-dữ-liệu-data-models).

#### B. `piratetok_live/helpers/like_accumulator.py` (`LikeAccumulator`)
*   **Vấn đề**: TikTok phân tán các sự kiện Like qua nhiều cụm máy chủ Shard. Trường `total` trong gói tin thường xuyên bị lệch pha/trễ, khiến tổng số like hiển thị bị nhảy lùi (ví dụ: 1000 -> 980 -> 1050).
*   **Giải thuật**:
    *   Theo dõi giá trị lớn nhất: `_max_total = max(_max_total, wire_total)` để đảm bảo số tổng luôn tăng đơn điệu.
    *   Cộng dồn từ trường delta đáng tin cậy: `_accumulated += delta`.
*   **Dữ liệu trả về**: Đối tượng [`LikeStats`](#5-cấu-trúc-các-model-dữ-liệu-data-models).

#### C. `piratetok_live/helpers/profile_cache.py` (`ProfileCache`)
*   Quản lý bộ nhớ đệm thông tin người dùng / avatar HD.
*   **Thread-Safe**: Sử dụng `threading.Lock()` bảo vệ mọi thao tác đọc/ghi cache.
*   **Negative Caching**: Khi tài khoản bị Private (`ProfilePrivateError`) hoặc không tồn tại (`ProfileNotFoundError`), lỗi cũng được lưu vào cache trong thời gian `ttl` (mặc định 300s) nhằm ngăn chặn việc gửi request cào lặp lại gây nghẽn và bị chặn IP.

---

### 3.6. `piratetok_live/http/`

Tầng giao tiếp HTTP, trích xuất dữ liệu Web và nhận diện môi trường.

#### A. `piratetok_live/http/api.py`
*   `check_online(username: str, timeout: float = 10.0, ...) -> RoomIdResult`:
    *   Gửi GET request tới `https://www.tiktok.com/api-live/user/room?uniqueId={username}`.
    *   Kiểm tra mã trạng thái:
        *   `statusCode == 19881007` -> Ném `UserNotFoundError`.
        *   `statusCode != 0` -> Ném `TikTokApiError`.
        *   `roomId == 0` hoặc `liveRoom.status != 2` và `user.status != 2` -> Ném `HostNotOnlineError`.
    *   Trả về `RoomIdResult(room_id)`.
*   `fetch_room_info(room_id: str, timeout: float = 10.0, cookies: str = "", ...) -> RoomInfo`:
    *   Gửi GET request tới `https://webcast.tiktok.com/webcast/room/info/?room_id={room_id}`.
    *   Xử lý mã lỗi `4003110` -> Ném `AgeRestrictedError` (phòng live 18+).
    *   Trích xuất: Tiêu đề, số người xem (`viewers`), số like, và danh sách link luồng FLV qua hàm `_parse_stream_urls()`.

#### B. `piratetok_live/http/sigi.py`
*   `scrape_profile(username: str, ttwid: str, ...) -> SigiProfile`:
    *   Tải mã nguồn HTML từ `https://www.tiktok.com/@{username}`.
    *   Gọi `_extract_sigi_json(html)`: Tìm thẻ `<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">` bằng thuật toán cắt chuỗi `find()` tốc độ cao (không dùng Regex/BeautifulSoup).
    *   Trích xuất dữ liệu từ `__DEFAULT_SCOPE__.webapp.user-detail`: HD Avatars (1080x1080, 720x720), User ID, Follower count, Following count, Like count, Video count, Bio link, Verified badge,...

#### C. `piratetok_live/http/ua.py`
*   `random_ua() -> str`: Chọn ngẫu nhiên User-Agent hiện đại (Chrome 131/132, Firefox 138/140 trên Windows, Mac, Linux).
*   `system_timezone() -> str`: Nhận diện múi giờ IANA của hệ thống qua Python `zoneinfo`, `/etc/timezone` hoặc `/etc/localtime`.
*   `system_locale() -> (lang, region)`: Nhận diện ngôn ngữ & quốc gia từ biến môi trường `LC_ALL` / `LANG`.

---

### 3.7. `piratetok_live/proto/`

Định nghĩa toàn bộ cấu trúc nhị phân theo chuẩn **Protocol Buffers v3** bằng cú pháp `betterproto`:

1.  **`schema.py`** (Các cấu trúc lõi & định danh):
    *   `WebcastPushFrame`: Frame bao ngoài cùng của mọi gói tin WebSocket.
    *   `WebcastResponse` & `ResponseMessage`: Danh sách thông điệp bên trong frame.
    *   `HeartbeatMessage` & `WebcastImEnterRoomMessage`: Gói tin nhịp tim và vào phòng.
    *   `User`, `UserHonor`, `FansClubMember`, `PayGrade`, `BadgeStruct`: Mô hình chi tiết người dùng, cấp bậc fan club, huy hiệu donate, cấp độ đại gia.
    *   `WebcastChatMessage`: Nội dung bình luận, icon cảm xúc (`emotes`), thông tin người gửi.
    *   `WebcastGiftMessage`: Chi tiết quà tặng, số lượng, combo, thông tin khay hiển thị (`GiftTrayInfo`), hiệu ứng chữ (`TextEffect`).
    *   `WebcastLikeMessage`: Lượt thả tim, màu sắc tim, số đếm.
    *   `WebcastMemberMessage`: Sự kiện vào phòng, cấp độ admin/moderator.
    *   `WebcastSocialMessage`: Sự kiện Follow và Share.
    *   `WebcastRoomUserSeqMessage`: Danh sách top khán giả đóng góp và tổng số người xem.
    *   `WebcastControlMessage`: Tín hiệu điều khiển phòng (kết thúc live, tạm dừng,...).

2.  **`messages.py`** (Các sự kiện mở rộng & chuyên biệt):
    *   `WebcastLinkMicBattle` & `WebcastLinkMicArmies`: Dữ liệu PK Battle / Đấu trường chiến binh giữa các streamer.
    *   `WebcastOecLiveShoppingMessage`: Dữ liệu ghim sản phẩm TikTok Shop.
    *   `WebcastPollMessage` & `WebcastEnvelopeMessage`: Bình chọn và Bao lì xì (Hộp quà may mắn).
    *   `WebcastRankUpdateMessage` & `WebcastHourlyRankMessage`: Cập nhật bảng xếp hạng giờ/ngày.
    *   `WebcastQuestionNewMessage`: Câu hỏi mới trong phần Q&A.
    *   `WebcastSubNotifyMessage`: Đăng ký hội viên (Subscriber).

---

### 3.8. `piratetok_live/errors.py`

Cây phân cấp ngoại lệ giúp bắt lỗi chính xác:

```
PirateTokError (Lớp cơ sở)
├── UserNotFoundError          # Streamer không tồn tại
├── HostNotOnlineError         # Streamer hiện không livestream
├── TikTokBlockedError         # Bị TikTok chặn HTTP (403, 429)
├── TikTokApiError             # Lỗi trả về từ API TikTok (statusCode != 0)
├── DeviceBlockedError         # Bị TikTok đánh dấu chặn thiết bị (DEVICE_BLOCKED)
├── AgeRestrictedError         # Phòng Live 18+ (cần session cookie)
├── ProfilePrivateError        # Trang cá nhân ở chế độ riêng tư
├── ProfileNotFoundError       # Không tìm thấy trang cá nhân
├── ProfileScrapeError         # Lỗi cấu trúc HTML khi scrape profile
└── ProfileError               # Lỗi API khi lấy dữ liệu profile
```

---

## 4. BẢNG MA TRẬN ĐẦY ĐỦ 72 SỰ KIỆN (EVENT REFERENCE MATRIX)

### 4.1. Nhóm Điều Khiển Vòng Đời & Sub-Routing (8 Sự Kiện)

| Tên Sự Kiện (`EventType.*`) | Nguồn Gốc / Protobuf Class | Ý Nghĩa Nghiệp Vụ |
| :--- | :--- | :--- |
| `connected` | *Local Client Event* | Kết nối WebSocket thành công tới phòng Live |
| `disconnected` | *Local Client Event* | Đã ngắt kết nối hoàn toàn khỏi phòng Live |
| `reconnecting` | *Local Client Event* | Đang trong tiến trình tự động thử kết nối lại |
| `unknown` | *Unmapped Webcast Message* | Nhận gói tin chưa có trong bảng ánh xạ hoặc giải mã lỗi |
| `follow` | Sub-routed từ `WebcastSocialMessage` (`action=1`) | Khán giả bấm Follow streamer |
| `share` | Sub-routed từ `WebcastSocialMessage` (`action=2..5`) | Khán giả bấm chia sẻ livestream |
| `join` | Sub-routed từ `WebcastMemberMessage` (`action=1`) | Khán giả mới tham gia vào phòng |
| `live_ended` | Sub-routed từ `WebcastControlMessage` (`action=3`) | Buổi livestream đã kết thúc |

### 4.2. Nhóm Cốt Lõi (Core Webcast Events - 7 Sự Kiện)

| Tên Sự Kiện (`EventType.*`) | Protobuf Class | Các Trường Dữ Liệu Quan Trọng |
| :--- | :--- | :--- |
| `chat` | `WebcastChatMessage` | `user`, `content`, `emotes`, `user_identity` |
| `gift` | `WebcastGiftMessage` | `user`, `gift`, `repeat_count`, `is_combo`, `diamond_total` |
| `like` | `WebcastLikeMessage` | `user`, `count`, `total`, `color` |
| `member` | `WebcastMemberMessage` | `user`, `member_count`, `action`, `is_set_to_admin` |
| `social` | `WebcastSocialMessage` | `user`, `action`, `share_count`, `follow_count` |
| `room_user_seq` | `WebcastRoomUserSeqMessage` | `viewer_count`, `total_user`, `ranks_list` |
| `control` | `WebcastControlMessage` | `action`, `tips`, `extra` |

### 4.3. Nhóm Hữu Ích (Useful Events - 5 Sự Kiện)

| Tên Sự Kiện (`EventType.*`) | Protobuf Class | Ý Nghĩa Nghiệp Vụ |
| :--- | :--- | :--- |
| `live_intro` | `WebcastLiveIntroMessage` | Giới thiệu phòng Live từ streamer |
| `room_message` | `WebcastRoomMessage` | Thông báo hệ thống trong phòng |
| `caption` | `WebcastCaptionMessage` | Phụ đề lời nói thời gian thực (Real-time subtitles) |
| `goal_update` | `WebcastGoalUpdateMessage` | Cập nhật tiến độ mục tiêu phòng Live (Goal progress) |
| `im_delete` | `WebcastImDeleteMessage` | Thu hồi / Xóa tin nhắn chat |

### 4.4. Nhóm Mở Rộng & Chuyên Biệt (Niche / Extended Events - 27 Sự Kiện)

| Tên Sự Kiện (`EventType.*`) | Protobuf Class | Ý Nghĩa Nghiệp Vụ |
| :--- | :--- | :--- |
| `rank_update` | `WebcastRankUpdateMessage` | Cập nhật thứ hạng của streamer |
| `poll` | `WebcastPollMessage` | Bình chọn / Thăm dò ý kiến khán giả |
| `envelope` | `WebcastEnvelopeMessage` | Rơi bao lì xì / Hộp kho báu may mắn |
| `room_pin` | `WebcastRoomPinMessage` | Ghim tin nhắn hoặc nội dung lên đầu phòng |
| `unauthorized_member` | `WebcastUnauthorizedMemberMessage` | Thông báo thành viên chưa xác thực |
| `link_mic_method` | `WebcastLinkMicMethod` | Tín hiệu kết nối Link Mic |
| `link_mic_battle` | `WebcastLinkMicBattle` | Bắt đầu / Kết thúc trận đấu PK Battle |
| `link_mic_armies` | `WebcastLinkMicArmies` | Điểm số đóng góp của đội quân trong trận PK |
| `link_message` | `WebcastLinkMessage` | Tin nhắn điều khiển Link Mic |
| `link_layer` | `WebcastLinkLayerMessage` | Thông tin tầng kết nối Link Layer |
| `link_mic_layout_state`| `WebcastLinkMicLayoutStateMessage`| Bố cục khung hình các khách mời Link Mic |
| `gift_panel_update` | `WebcastGiftPanelUpdateMessage` | Cập nhật bảng danh sách quà tặng |
| `in_room_banner` | `WebcastInRoomBannerMessage` | Banner quảng cáo hiển thị trong phòng |
| `guide` | `WebcastGuideMessage` | Hướng dẫn tương tác cho khán giả |
| `emote_chat` | `WebcastEmoteChatMessage` | Khán giả gửi sticker / emoji tùy chỉnh |
| `question_new` | `WebcastQuestionNewMessage` | Khán giả đặt câu hỏi mới trong Q&A |
| `sub_notify` | `WebcastSubNotifyMessage` | Thông báo đăng ký hội viên Subscriber |
| `barrage` | `WebcastBarrageMessage` | Hiệu ứng mưa tin nhắn / Pháo hoa |
| `hourly_rank` | `WebcastHourlyRankMessage` | Bảng xếp hạng theo giờ |
| `msg_detect` | `WebcastMsgDetectMessage` | Gói tin kiểm tra chất lượng đường truyền |
| `link_mic_fan_ticket` | `WebcastLinkMicFanTicketMethod` | Điểm fan ticket trong trận PK |
| `room_verify` | `RoomVerifyMessage` | Xác thực phòng Live |
| `oec_live_shopping` | `WebcastOecLiveShoppingMessage` | Sự kiện TikTok Shop (Ghim sản phẩm, mua hàng) |
| `gift_broadcast` | `WebcastGiftBroadcastMessage` | Phát sóng thông báo quà tặng lớn toàn server |
| `rank_text` | `WebcastRankTextMessage` | Nội dung chữ hiển thị xếp hạng |
| `gift_dynamic_restriction`| `WebcastGiftDynamicRestrictionMessage`| Giới hạn động đối với quà tặng |
| `viewer_picks_update` | `WebcastViewerPicksUpdateMessage` | Cập nhật danh sách khán giả được chọn |

### 4.5. Nhóm Phụ Trợ (Secondary Events - 25 Sự Kiện)

| Tên Sự Kiện (`EventType.*`) | Protobuf Class | Ý Nghĩa Nghiệp Vụ |
| :--- | :--- | :--- |
| `access_control` | `WebcastAccessControlMessage` | Kiểm soát quyền truy cập / Captcha |
| `access_recall` | `WebcastAccessRecallMessage` | Thu hồi quyền truy cập |
| `alert_box_audit_result`| `WebcastAlertBoxAuditResultMessage`| Kết quả kiểm duyệt hộp thông báo |
| `binding_gift` | `WebcastBindingGiftMessage` | Quà tặng ràng buộc sự kiện |
| `boost_card` | `WebcastBoostCardMessage` | Thẻ tăng tốc / Boost tương tác |
| `bottom` | `WebcastBottomMessage` | Thông báo hiển thị ở đáy màn hình |
| `game_rank_notify` | `WebcastGameRankNotifyMessage` | Thông báo bảng xếp hạng game |
| `gift_prompt` | `WebcastGiftPromptMessage` | Gợi ý tặng quà |
| `link_state` | `WebcastLinkStateMessage` | Trạng thái kết nối khách mời |
| `link_mic_battle_punish_finish`| `WebcastLinkMicBattlePunishFinish`| Kết thúc hình phạt trận đấu PK |
| `linkmic_battle_task` | `WebcastLinkmicBattleTaskMessage` | Nhiệm vụ trong trận đấu PK |
| `marquee_announcement` | `WebcastMarqueeAnnouncementMessage` | Chữ chạy thông báo (Marquee) |
| `notice` | `WebcastNoticeMessage` | Thông báo quan trọng từ nền tảng |
| `notify` | `WebcastNotifyMessage` | Thông báo chung |
| `partnership_drops_update`| `WebcastPartnershipDropsUpdateMessage`| Cập nhật quà rơi từ đối tác Game Drops |
| `partnership_game_offline`| `WebcastPartnershipGameOfflineMessage`| Game đối tác dừng hoạt động |
| `partnership_punish` | `WebcastPartnershipPunishMessage` | Xử phạt vi phạm đối tác |
| `perception` | `WebcastPerceptionMessage` | Cảnh báo vi phạm nội dung livestream |
| `speaker` | `WebcastSpeakerMessage` | Thông báo qua loa phát thanh |
| `sub_capsule` | `WebcastSubCapsuleMessage` | Khung hiển thị đăng ký hội viên |
| `sub_pin_event` | `WebcastSubPinEventMessage` | Sự kiện ghim thông tin hội viên |
| `subscription_notify` | `WebcastSubscriptionNotifyMessage` | Thông báo gia hạn / đăng ký hội viên |
| `toast` | `WebcastToastMessage` | Thông báo Toast nhanh trên màn hình |
| `system` | `WebcastSystemMessage` | Thông báo hệ thống |
| `live_game_intro` | `WebcastLiveGameIntroMessage` | Giới thiệu trò chơi đang livestream |

---

## 5. CẤU TRÚC CÁC MODEL DỮ LIỆU (DATA MODELS)

### 5.1. `SigiProfile` (`piratetok_live.http.sigi`)
Mô hình thông tin người dùng được trích xuất từ SIGI state:
*   `user_id: str`: ID định danh người dùng.
*   `unique_id: str`: Username (@handle).
*   `nickname: str`: Tên hiển thị.
*   `bio: str`: Tiểu sử.
*   `avatar_thumb: str`, `avatar_medium: str`, `avatar_large: str`: Link ảnh đại diện (đặc biệt `avatar_large` là ảnh HD 720x720 / 1080x1080).
*   `verified: bool`: Đã xác minh tích xanh.
*   `private_account: bool`: Tài khoản riêng tư.
*   `is_organization: bool`: Tài khoản tổ chức / doanh nghiệp.
*   `room_id: str`: ID phòng Live nếu đang phát trực tiếp.
*   `bio_link: Optional[str]`: Link gắn trên tiểu sử.
*   `follower_count: int`, `following_count: int`, `heart_count: int`, `video_count: int`, `friend_count: int`: Các chỉ số thống kê.

### 5.2. `RoomInfo` & `StreamUrls` (`piratetok_live.http.api`)
*   `RoomInfo`:
    *   `title: str`: Tiêu đề buổi livestream.
    *   `viewers: int`: Số người đang xem trực tiếp.
    *   `likes: int`: Tổng lượt thích.
    *   `total_user: int`: Tổng lượt người đã ghé xem.
    *   `stream_url: Optional[StreamUrls]`: Danh sách luồng video phát trực tiếp.
*   `StreamUrls`:
    *   `flv_origin: str`: Luồng FLV gốc (Full HD 1080p).
    *   `flv_hd: str`: Luồng FLV chuẩn HD (720p).
    *   `flv_sd: str`: Luồng FLV chuẩn SD (480p).
    *   `flv_ld: str`: Luồng FLV độ phân giải thấp (360p).
    *   `flv_audio: str`: Luồng chỉ có âm thanh (Audio only).

### 5.3. `GiftStreakEvent` (`piratetok_live.helpers.gift_streak`)
*   `streak_id: int`: ID nhóm chuỗi quà (`group_id`).
*   `is_active: bool`: Chuỗi combo còn đang tiếp diễn hay không.
*   `is_final: bool`: Đã kết thúc chuỗi quà hay chưa.
*   `event_gift_count: int`: Số lượng quà **mới phát sinh** trong lần nhận này (Delta).
*   `total_gift_count: int`: Tổng số quà tích lũy trong chuỗi.
*   `event_diamond_count: int`: Số kim cương **mới phát sinh** trong lần nhận này.
*   `total_diamond_count: int`: Tổng số kim cương tích lũy trong chuỗi.

### 5.4. `LikeStats` (`piratetok_live.helpers.like_accumulator`)
*   `event_like_count: int`: Số lượt thả tim trong sự kiện vừa nhận (Delta).
*   `total_like_count: int`: Tổng số lượt thích đã được chuẩn hóa đơn điệu (Monotonic Max).
*   `accumulated_count: int`: Tổng số lượt thích được cộng dồn thủ công từ các delta.
*   `went_backwards: bool`: Cờ đánh dấu phát hiện gói tin từ server shard bị nhảy lùi số lượng.

### 5.5. `ProductInfo` (`piratetok_live.events.types`)
*   `product_id: str`: Mã ID định danh duy nhất của sản phẩm trên TikTok Shop toàn cầu.
*   `title: str`: Tên sản phẩm Tiếng Việt đầy đủ có dấu chuẩn SEO.
*   `url: str`: Đường link trực tiếp mở trang mua hàng không dính Captcha.
*   `image: str`: Link ảnh bìa đại diện Thumbnail #1 HD độ phân giải cao (1200x1200).
*   `images: List[str]`: Danh sách toàn bộ ảnh chi tiết trong bộ sưu tập gallery (đúng thứ tự tuần tự).
*   `seller: str`: Tên gian hàng / Đơn vị bán hàng chính hãng.
*   `sold_count: str`: Tổng số lượng sản phẩm đã bán ra trên sàn.

---


## 6. SỔ TAY HƯỚNG DẪN BẢO TRÌ & XỬ LÝ SỰ CỐ

### 6.1. Khi TikTok thêm hoặc đổi trường dữ liệu trong Protobuf
1. Mở file [piratetok_live/proto/schema.py](file:///d:/Workspace/livepy/piratetok_live/proto/schema.py) hoặc [piratetok_live/proto/messages.py](file:///d:/Workspace/livepy/piratetok_live/proto/messages.py).
2. Tìm class Protobuf tương ứng và thêm trường mới theo cú pháp `betterproto`:
   ```python
   @dataclass(eq=False, repr=False)
   class WebcastChatMessage(betterproto.Message):
       # ... các trường hiện tại ...
       custom_field: str = betterproto.string_field(99) # 99 là Field Index trong file .proto gốc
   ```

### 6.2. Khi TikTok thêm loại sự kiện mới
1. Khai báo tên sự kiện trong [piratetok_live/events/types.py](file:///d:/Workspace/livepy/piratetok_live/events/types.py):
   ```python
   class EventType:
       my_new_event = "my_new_event"
   ```
2. Định nghĩa class Protobuf trong `piratetok_live/proto/messages.py`.
3. Khai báo ánh xạ trong `_METHOD_MAP` tại [piratetok_live/events/router.py](file:///d:/Workspace/livepy/piratetok_live/events/router.py):
   ```python
   _METHOD_MAP["WebcastMyNewEventMessage"] = EventType.my_new_event
   ```

### 6.3. Xử lý lỗi chặn thiết bị `DEVICE_BLOCKED` hoặc HTTP 415
*   **Nguyên nhân**: Máy chủ TikTok phát hiện TTWID đã bị cắm cờ hoặc IP gửi request quá dày đặc.
*   **Giải pháp**:
    1. Thư viện đã tích hợp cơ chế tự động bắt lỗi `DeviceBlockedError`, cấp lại `ttwid` mới và đổi User-Agent ngẫu nhiên sau 2 giây.
    2. Nếu bị chặn liên tục trên IP cố định, hãy truyền proxy:
       ```python
       client.proxy("http://user:password@proxy-ip:port")
       ```
    3. Hoặc lấy cookie `ttwid` trực tiếp từ trình duyệt thật và truyền vào:
       ```python
       client.cookies("ttwid=1%7C...")
       ```

### 6.4. Xử lý lỗi `ProfileScrapeError` khi cào Avatar HD
*   **Nguyên nhân**: TikTok cập nhật mã nguồn HTML làm đổi tên thẻ script chứa SIGI JSON.
*   **Kiểm tra**: Mở [piratetok_live/http/sigi.py](file:///d:/Workspace/livepy/piratetok_live/http/sigi.py), kiểm tra hằng số `_SIGI_MARKER = 'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"'` và cập nhật theo thẻ script mới trong mã nguồn trang TikTok Profile.

---

## 7. CÁC KỊCH BẢN SỬ DỤNG MẪU (USAGE EXAMPLES)

### 7.1. Kết nối cơ bản & Lắng nghe Chat / Quà tặng
```python
import asyncio
from piratetok_live import TikTokLiveClient, EventType

async def main():
    client = TikTokLiveClient("swatchesbybaobao")

    @client.on(EventType.connected)
    def on_connected(evt):
        print(f"=== KẾT NỐI THÀNH CÔNG PHÒNG: {evt.room_id} ===")

    @client.on(EventType.chat)
    def on_chat(evt):
        user = evt.data.get("user", {}).get("nickname", "Ẩn danh")
        msg = evt.data.get("content", "")
        print(f"[Chat] {user}: {msg}")

    @client.on(EventType.gift)
    def on_gift(evt):
        user = evt.data.get("user", {}).get("nickname", "Ẩn danh")
        gift = evt.data.get("gift", {}).get("name", "Quà")
        count = evt.data.get("repeat_count", 1)
        print(f"[Gift] {user} đã tặng {count}x {gift} (Tổng kim cương: {evt.data.get('diamond_total')})")

    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())
```

### 7.2. Tích hợp `GiftStreakTracker` và `LikeAccumulator`
```python
from piratetok_live import TikTokLiveClient, EventType, GiftStreakTracker, LikeAccumulator

client = TikTokLiveClient("swatchesbybaobao")
streak_tracker = GiftStreakTracker()
like_acc = LikeAccumulator()

@client.on(EventType.gift)
def on_gift(evt):
    # Tính chính xác số lượng quà mới nhận trong đợt combo này
    res = streak_tracker.process(evt.data)
    if res.event_gift_count > 0:
        print(f"[Combo] +{res.event_gift_count} quà mới (Tổng streak: {res.total_gift_count}, +{res.event_diamond_count} kim cương)")

@client.on(EventType.like)
def on_like(evt):
    # Khắc phục hiện tượng like nhảy lùi
    stats = like_acc.process(evt.data)
    print(f"[Like] +{stats.event_like_count} like mới -> Tổng like chuẩn hóa: {stats.total_like_count}")
```

### 7.3. Lấy thông tin phòng & Link luồng phát trực tiếp (Stream URLs)
```python
from piratetok_live import TikTokLiveClient

# 1. Kiểm tra online
room = TikTokLiveClient.check_online("swatchesbybaobao")
print(f"Streamer đang phát Live tại Room ID: {room.room_id}")

# 2. Lấy metadata phòng và link luồng RTMP/FLV
info = TikTokLiveClient.fetch_room_info(room.room_id)
print(f"Tiêu đề: {info.title}")
print(f"Số người xem: {info.viewers} | Lượt like: {info.likes}")
if info.stream_url:
    print(f"Link Full HD: {info.stream_url.flv_origin}")
    print(f"Link HD 720p: {info.stream_url.flv_hd}")
```

### 7.4. Giám sát Giỏ Hàng & Bóc Tách Sản Phẩm TikTok Shop (OEC Live Shopping)
```python
import asyncio
from piratetok_live import TikTokLiveClient, EventType, get_ttwid

async def main():
    username = "swatchesbybaobao"
    client = TikTokLiveClient(username)
    
    # Cấp token TTWID xác thực an toàn
    client.cookies(f"ttwid={get_ttwid(username)}")

    active_product_id = ""

    @client.on(EventType.oec_live_shopping)
    def on_shop(evt):
        nonlocal active_product_id
        
        # Bóc tách Product ID mới hoặc duy trì trạng thái ghim hiện tại
        if evt.product_id:
            active_product_id = evt.product_id
            
        # Tự động trích xuất thông tin SEO, Tên tiếng Việt gốc, Ảnh Thumbnail #1 HD, Gian hàng và Lượt bán
        info = evt.canonical_product_info(region="vn")
        
        print("\n" + "🔥" * 45)
        print("[🛍️ TIKTOK SHOP - PHÁT HIỆN SỰ KIỆN GIỎ HÀNG / GHIM SẢN PHẨM!]")
        if info.title:
            print(f"  📦 Tên Sản Phẩm: {info.title}")
        if info.product_id or active_product_id:
            print(f"  🆔 Mã Sản Phẩm: {info.product_id or active_product_id}")
        if info.seller:
            print(f"  🏪 Gian Hàng: {info.seller}")
        if info.sold_count:
            print(f"  📈 Lượt Bán: {info.sold_count}")
        if info.image:
            print(f"  🖼️ Ảnh Bìa (Thumbnail #1 HD): {info.image}")
        if info.url:
            print(f"  🔗 Link Mua Hàng (Không Captcha): {info.url}")
        print("🔥" * 45 + "\n")

    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())
```


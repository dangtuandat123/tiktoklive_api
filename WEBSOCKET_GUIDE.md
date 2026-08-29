# 📘 HƯỚNG DẪN TÍCH HỢP TIKTOK LIVE WEBSOCKET GATEWAY (`ws_server.py`)

Tài liệu hướng dẫn kết nối và tích hợp máy chủ **TikTok Live WebSocket Gateway** vào các hệ thống bên ngoài (**Node.js, C# / .NET, PHP, Python, Go, Unity, Web Frontend / React / Vue, OBS Browser Source**).

---

## 1. KHỞI CHẠY MÁY CHỦ GATEWAY

Chạy lệnh trong thư mục dự án:

```bash
# Chạy mặc định trên ws://0.0.0.0:8765
python ws_server.py

# Hoặc tùy chỉnh cổng / Proxy nếu cần:
python ws_server.py --port 9000 --proxy "http://127.0.0.1:8080"
```

> **💡 Lưu ý:** Máy chủ có cơ chế **Gộp kết nối (Connection Multiplexing)**: Dù bạn có 100 client kết nối vào cùng theo dõi một streamer `@username`, hệ thống chỉ mở **duy nhất 1 kết nối tới TikTok** và phát lại cho tất cả client ➔ Tiết kiệm 99% băng thông và tránh bị TikTok chặn IP.

---

## 2. ĐẶC TẢ GIAO THỨC KẾT NỐI (PROTOCOL SPECIFICATION)

### 2.1. Cách 1: Kết Nối Nhanh Bằng URL Query Param (Khuyên Dùng)
Chỉ cần mở kết nối WebSocket tới URL:
```text
ws://localhost:8765/live?username=<streamer_username>
```
*Ví dụ:* `ws://localhost:8765/live?username=swatchesbybaobao`
*(Server sẽ tự động đăng ký phòng và phát dữ liệu ngay lập tức).*

---

### 2.2. Cách 2: Kết Nối & Gửi Lệnh Điều Khiển JSON (Command Pattern)
Mở kết nối tới `ws://localhost:8765` và gửi các thông điệp JSON:

#### 1. Đăng ký nhận sự kiện phòng:
```json
{
  "action": "subscribe",
  "username": "swatchesbybaobao"
}
```

#### 2. Hủy đăng ký nhận sự kiện:
```json
{
  "action": "unsubscribe",
  "username": "swatchesbybaobao"
}
```

#### 3. Kiểm tra trạng thái phòng:
```json
{
  "action": "get_room_status",
  "username": "swatchesbybaobao"
}
```

#### 4. Xem danh sách các phòng đang theo dõi:
```json
{
  "action": "list_rooms"
}
```

#### 5. Kiểm tra tải Gateway (Stats):
```json
{
  "action": "stats"
}
```

#### 6. Giữ kết nối (Ping):
```json
{
  "action": "ping"
}
```
*(Server phản hồi: `{"event": "pong", "server_time": "..."}`)*.

---

## 3. ĐỊNH DẠNG DỮ LIỆU SỰ KIỆN PHÁT RA (JSON SCHEMAS)

Mọi gói tin server gửi về đều tuân theo chuẩn:
```json
{
  "event": "<tên_sự_kiện>",
  "username": "<streamer_username>",
  "room_id": "<mã_phòng_live>",
  "timestamp": "2026-08-29T08:30:00.123Z",
  "data": { ... }
}
```

---

### 3.1. Sự Kiện Bình Luận Chat (`event: "chat"`)
```json
{
  "event": "chat",
  "username": "swatchesbybaobao",
  "room_id": "7679237785261837074",
  "timestamp": "2026-08-29T08:30:00.123Z",
  "data": {
    "user": {
      "id": "111222333",
      "nickname": "Nguyễn Văn A",
      "unique_id": "nguyenvana",
      "sec_uid": "MS4wLjABAAAA...",
      "avatar_url": "https://p16-sign-va.tiktokcdn.com/...",
      "is_host": false,
      "is_mod": true,
      "is_sub": false,
      "is_fan": true,
      "fan_club": {
        "name": "Fan Cứng",
        "level": 12
      }
    },
    "comment": "Sản phẩm này dùng có trắng da không chị?"
  }
}
```

---

### 3.2. Sự Kiện Giỏ Hàng TikTok Shop (`event: "oec_live_shopping"`)
```json
{
  "event": "oec_live_shopping",
  "username": "swatchesbybaobao",
  "room_id": "7679237785261837074",
  "timestamp": "2026-08-29T08:30:05.456Z",
  "data": {
    "action_type": 1,
    "action_name": "SetPinProduct (Ghim sản phẩm mới)",
    "product_id": "1734309253794202883",
    "product_title": "[LIVE 2] Sữa dưỡng thể Olay trắng da 260g (Hàng nội địa Trung Quốc chính hãng)",
    "product_image": "https://p16-oec-sg.ibyteimg.com/tos-alisg-i-aphluv4xwc-sg/c2864aa520f14d028df4effe3ae12908~tplv-aphluv4xwc-crop-webp:1200:1200.webp",
    "product_images": [
      "https://p16-oec-sg.ibyteimg.com/tos-alisg-i-aphluv4xwc-sg/c2864aa520f14d028df4effe3ae12908~tplv-aphluv4xwc-crop-webp:1200:1200.webp"
    ],
    "product_url": "https://shop.tiktok.com/vn/pdp/olay-body-cellscience-b5-duong-co-the-san-xuat-tai-china/1734309253794202883?source=product_detail&enter_method=url_semantic_301",
    "seller": "P&G Beauty Việt Nam - eMesa",
    "sold_count": "126.2K đã bán"
  }
}
```

---

### 3.3. Sự Kiện Quà Tặng & Combo Streak (`event: "gift"`)
```json
{
  "event": "gift",
  "username": "swatchesbybaobao",
  "room_id": "7679237785261837074",
  "timestamp": "2026-08-29T08:30:10.789Z",
  "data": {
    "user": {
      "id": "222333444",
      "nickname": "Đại Gia 999",
      "avatar_url": "https://..."
    },
    "gift": {
      "id": 5655,
      "name": "Hoa Hồng",
      "diamond_count": 1,
      "image_url": "https://..."
    },
    "combo": {
      "streak_id": 1001,
      "is_active": true,
      "is_final": false,
      "event_gift_count": 5,
      "total_gift_count": 20,
      "event_diamond_count": 5,
      "total_diamond_count": 20
    }
  }
}
```

---

### 3.4. Sự Kiện Thả Tim (`event: "like"`)
```json
{
  "event": "like",
  "username": "swatchesbybaobao",
  "room_id": "7679237785261837074",
  "timestamp": "2026-08-29T08:30:12.123Z",
  "data": {
    "user": { "nickname": "Khán giả" },
    "event_like_count": 5,
    "total_like_count": 125430
  }
}
```

---

### 3.5. Sự Kiện Thống Kê Người Xem (`event: "room_user_seq"`)
```json
{
  "event": "room_user_seq",
  "username": "swatchesbybaobao",
  "room_id": "7679237785261837074",
  "timestamp": "2026-08-29T08:30:15.000Z",
  "data": {
    "viewer_count": 132,
    "total_users": 69450,
    "top_ranks": [
      { "nickname": "blaise2968", "score": 36, "rank": 1 },
      { "nickname": "User_ABC", "score": 20, "rank": 2 }
    ]
  }
}
```

---

## 4. CODE MẪU TÍCH HỢP TỪNG NGÔN NGỮ

### 4.1. Node.js / TypeScript / JavaScript (Dùng thư viện `ws`)

Cài đặt: `npm install ws`

```javascript
const WebSocket = require('ws');

const USERNAME = 'swatchesbybaobao';
const WS_URL = `ws://localhost:8765/live?username=${USERNAME}`;

function connect() {
  const ws = new WebSocket(WS_URL);

  ws.on('open', () => {
    console.log(`[+] Đã kết nối WebSocket Gateway tới phòng @${USERNAME}`);
  });

  ws.on('message', (rawData) => {
    try {
      const msg = JSON.parse(rawData);
      const event = msg.event;
      const data = msg.data || {};

      switch (event) {
        case 'chat':
          console.log(`💬 [CHAT] ${data.user.nickname}: ${data.comment}`);
          break;

        case 'gift':
          console.log(`🎁 [GIFT] ${data.user.nickname} tặng ${data.gift.name} (x${data.combo.total_gift_count}) - ${data.combo.total_diamond_count} 💎`);
          break;

        case 'like':
          console.log(`❤️ [LIKE] Tổng tim: ${data.total_like_count.toLocaleString()}`);
          break;

        case 'oec_live_shopping':
          console.log(`🛍️ [SHOP] Ghim sản phẩm: ${data.product_title}`);
          console.log(`   🔗 Link mua: ${data.product_url}`);
          break;

        case 'caption':
          console.log(`🎙️ [PHỤ ĐỀ AI]: ${data.content}`);
          break;

        case 'error':
          console.error(`❌ [LỖI]: [${data.code}] ${data.message}`);
          break;
      }
    } catch (e) {
      console.error('Lỗi parse JSON:', e);
    }
  });

  ws.on('close', () => {
    console.log('[-] Kết nối bị ngắt, đang thử kết nối lại sau 3s...');
    setTimeout(connect, 3000);
  });

  ws.on('error', (err) => {
    console.error('Lỗi socket:', err.message);
  });
}

connect();
```

---

### 4.2. C# / .NET (Sử dụng `ClientWebSocket`)

```csharp
using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

class Program
{
    static async Task Main(string[] args)
    {
        string username = "swatchesbybaobao";
        Uri serverUri = new Uri($"ws://localhost:8765/live?username={username}");

        using ClientWebSocket ws = new ClientWebSocket();
        Console.WriteLine($"Đang kết nối tới: {serverUri}...");
        await ws.ConnectAsync(serverUri, CancellationToken.None);
        Console.WriteLine("[+] Kết nối thành công! Đang chờ sự kiện...");

        byte[] buffer = new byte[8192];
        while (ws.State == WebSocketState.Open)
        {
            var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
            if (result.MessageType == WebSocketMessageType.Text)
            {
                string jsonString = Encoding.UTF8.GetString(buffer, 0, result.Count);
                using JsonDocument doc = JsonDocument.Parse(jsonString);
                string evtType = doc.RootElement.GetProperty("event").GetString();
                JsonElement data = doc.RootElement.GetProperty("data");

                if (evtType == "chat")
                {
                    string nick = data.GetProperty("user").GetProperty("nickname").GetString();
                    string comment = data.GetProperty("comment").GetString();
                    Console.WriteLine($"💬 [CHAT] {nick}: {comment}");
                }
                else if (evtType == "oec_live_shopping")
                {
                    string title = data.GetProperty("product_title").GetString();
                    string url = data.GetProperty("product_url").GetString();
                    Console.WriteLine($"🛍️ [TIKTOK SHOP] {title}\n   Link: {url}");
                }
            }
        }
    }
}
```

---

### 4.3. PHP (Sử dụng `workerman/workerman` hoặc `textalk/websocket`)

```php
<?php
require 'vendor/autoload.php';

use WebSocket\Client;

$username = "swatchesbybaobao";
$client = new Client("ws://localhost:8765/live?username=" . $username);

echo "[+] Đã kết nối WebSocket Gateway thành công!\n";

while (true) {
    try {
        $message = $client->receive();
        $msg = json_decode($message, true);
        $event = $msg['event'] ?? '';
        $data = $msg['data'] ?? [];

        if ($event === 'chat') {
            echo "💬 [CHAT] " . $data['user']['nickname'] . ": " . $data['comment'] . "\n";
        } elseif ($event === 'oec_live_shopping') {
            echo "🛍️ [SHOP] Ghim: " . $data['product_title'] . "\n";
            echo "   🔗 Link: " . $data['product_url'] . "\n";
        }
    } catch (\Exception $e) {
        echo "Lỗi: " . $e->getMessage() . "\n";
        break;
    }
}
```

---

### 4.4. Go (Golang - Sử dụng `gorilla/websocket`)

```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"github.com/gorilla/websocket"
)

type GatewayEvent struct {
	Event    string                 `json:"event"`
	Username string                 `json:"username"`
	Data     map[string]interface{} `json:"data"`
}

func main() {
	username := "swatchesbybaobao"
	url := fmt.Sprintf("ws://localhost:8765/live?username=%s", username)

	c, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		log.Fatal("Lỗi kết nối:", err)
	}
	defer c.Close()

	fmt.Println("[+] Đã kết nối WebSocket Gateway thành công!")

	for {
		_, message, err := c.ReadMessage()
		if err != nil {
			log.Println("Lỗi đọc message:", err)
			return
		}

		var evt GatewayEvent
		json.Unmarshal(message, &evt)

		if evt.Event == "chat" {
			user := evt.Data["user"].(map[string]interface{})
			fmt.Printf("💬 [CHAT] %s: %s\n", user["nickname"], evt.Data["comment"])
		} else if evt.Event == "oec_live_shopping" {
			fmt.Printf("🛍️ [SHOP] %s | Link: %s\n", evt.Data["product_title"], evt.Data["product_url"])
		}
	}
}
```

---

### 4.5. Web Frontend / HTML5 / React / Vue / OBS Overlay

```javascript
// Kết nối trực tiếp từ trình duyệt
const socket = new WebSocket('ws://localhost:8765/live?username=swatchesbybaobao');

socket.onopen = () => {
  console.log('🟢 Đã kết nối Gateway thành công!');
};

socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.event === 'chat') {
    // Hiển thị tin nhắn chat lên DOM
    renderChat(msg.data.user.nickname, msg.data.comment);
  } else if (msg.event === 'gift') {
    // Hiệu ứng quà tặng bay trên màn hình
    triggerGiftAnimation(msg.data);
  } else if (msg.event === 'oec_live_shopping') {
    // Hiển thị Pop-up sản phẩm đang ghim
    showProductCard(msg.data);
  }
};
```

---

## 5. BẢNG MÃ LỖI CHUẨN (ERROR CODES)

Khi có lỗi xảy ra, server sẽ gửi sự kiện `event: "error"` kèm mã lỗi cấu trúc chuẩn:

| Mã Lỗi (`code`) | Ý Nghĩa | Hướng Xử Lý Khuyên Dùng |
| :--- | :--- | :--- |
| `HOST_NOT_ONLINE` | Streamer hiện đang tắt live hoặc chưa phát sóng | Chờ và thử lại sau 1-2 phút |
| `USER_NOT_FOUND` | Tên tài khoản TikTok không tồn tại | Kiểm tra lại chính tả username |
| `DEVICE_BLOCKED` | TikTok cắm cờ token TTWID (HTTP 415) | Server tự động xoay token mới qua Playwright |
| `RATE_LIMITED` | Quá tải kết nối trên 1 địa chỉ IP (HTTP 429) | Dùng thêm danh sách Proxy trong `ws_server.py` |
| `IP_BLOCKED` | IP bị tường lửa TikTok chặn (HTTP 403) | Đổi IP mạng hoặc dùng Proxy |
| `NETWORK_TIMEOUT` | Mạng chập chờn / Quá thời gian chờ | Server tự động kết nối lại |

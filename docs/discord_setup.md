# Hướng dẫn tích hợp Discord — Điều khiển Network AI Assistant từ xa

## 🎯 Mục tiêu
Sau khi hoàn thành, bạn sẽ:
- Chạy AI Agent trên máy tính (terminal)
- Từ **điện thoại** hoặc bất kỳ đâu, chỉ cần mở Discord và chat là điều khiển được thiết bị mạng

---

## 📦 Bước 1: Cài thư viện Discord

```bash
cd /home/khangpham/AI/AAN
source venv/bin/activate  # hoặc venv\\Scripts\\activate trên Windows
pip install discord.py python-dotenv
```

> **Lưu ý:** `discord.py` phiên bản >= 2.3.0 yêu cầu Python >= 3.8

---

## 🤖 Bước 2: Tạo Bot Discord

### 2.1 Vào Discord Developer Portal
Mở trình duyệt: https://discord.com/developers/applications

### 2.2 Tạo Application mới
1. Click **"New Application"**
2. Đặt tên: `Network AI Bot`
3. Tick ô điều khoản → **Create**

### 2.3 Lấy Bot Token
1. Vào tab **"Bot"** ở sidebar trái
2. Click **"Reset Token"** (hoặc "Copy" nếu đã có)
3. **Lưu token này cẩn thận** — đây là "mật khẩu" của bot

### 2.4 Bật quyền Message Content Intent
1. Trong tab **Bot**, cuộn xuống phần **Privileged Gateway Intents**
2. **Bật** công tắc **"MESSAGE CONTENT INTENT"**
3. Click **"Save Changes"**

> ⚠️ **KHÔNG được tắt intent này!** Bot sẽ không đọc được tin nhắn nếu thiếu.

### 2.5 Mở bot vào server của bạn
1. Vào tab **"OAuth2"** → **"URL Generator"**
2. Trong **Scopes**, tick **"bot"**
3. Trong **Bot Permissions**, tick:
   - ✅ Send Messages
   - ✅ Read Message History
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Read Messages / View Channels
4. Copy URL ở cuối trang, mở trong trình duyệt
5. Chọn server → **Authorize**

---

## ⚙️ Bước 3: Cấu hình file `.env`

Copy file mẫu:
```bash
cp .env.example .env
```

Sửa file `.env` bằng editor:
```env
DISCORD_BOT_TOKEN=MTAxxx...  # Dán token bạn vừa copy
DISCORD_CHANNEL_ID=1234567890123456789  # ID của channel muốn bot hoạt động
DISCORD_PREFIX=!net
```

### Lấy Channel ID:
1. Trong Discord, bật **Developer Mode**: User Settings → Advanced → Developer Mode (ON)
2. Right-click vào channel → **Copy Channel ID**
3. Dán vào `.env`

> **Ghi chú:** Nếu để `DISCORD_CHANNEL_ID=` (trống), bot sẽ phản hồi **mọi tin nhắn** ở mọi channel. Khuyến nghị giới hạn 1 channel để tránh spam.

---

## 🚀 Bước 4: Chạy Bot

### Chạy Discord Bot (trên terminal):
```bash
source venv/bin/activate
python -m src.discord_bot
```

Bạn sẽ thấy log:
```
INFO | Bot đã đăng nhập với tên: Network AI Bot#1234
INFO | Đang khởi tạo Network AI Agent...
INFO | [HỆ THỐNG] Khởi tạo hoàn tất!
INFO | [OK] Network AI Agent đã sẵn sàng!
```

---

## 📱 Bước 5: Chat từ điện thoại

Mở Discord trên điện thoại, vào channel đã cấu hình, gõ:

```
!net show ip interface brief
```

Hoặc nếu bạn đã đặt `DISCORD_CHANNEL_ID`, chỉ cần gõ trực tiếp:
```
show ip interface brief
```

Bot sẽ phản hồi với:
- Phần **phân tích** từ AI
- Phần **dữ liệu thô** từ thiết bị Cisco

---

## 🔧 Các lệnh hỗ trợ

| Lệnh | Mô tả |
|------|-------|
| `!net <yêu cầu>` | Chạy agent với câu hỏi / lệnh |
| `!net status` | Kiểm tra trạng thái hệ thống |

---

## 🛠️ Xử lý lỗi thường gặp

### Lỗi: `discord.errors.PrivilegedIntentsRequired`
→ Bạn chưa bật **Message Content Intent** ở Bước 2.4

### Lỗi: `Login failure: Improper token`
→ Token trong `.env` bị sai hoặc thiếu. Copy lại từ Developer Portal.

### Lỗi: Bot online nhưng không trả lờii
→ Kiểm tra `DISCORD_CHANNEL_ID` có đúng không, hoặc thử dùng prefix `!net ` rõ ràng.

### Lỗi: `Khởi tạo Agent thất bại`
→ GNS3 chưa chạy, hoặc IP/Project ID trong `core_engine.py` không đúng.

---

## 🔄 Chạy song song Terminal + Discord

Bạn có thể chạy **cả hai cùng lúc**:
- Terminal: `python -m src.main` → giao diện Rich đẹp mắt
- Terminal khác: `python -m src.discord_bot` → lắng nghe Discord

Cả hai đều dùng chung logic `core_engine.py`, không xung đột.


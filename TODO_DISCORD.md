# TODO — Tích hợp Discord vào Network AI Assistant

## ✅ Đã có sẵn (không cần sửa)
- [x] `src/core_engine.py` — Logic lõi dùng chung
- [x] `src/discord_bot.py` — Discord Bot async
- [x] `.env.example` — Mẫu biến môi trường
- [x] `docs/discord_setup.md` — Hướng dẫn chi tiết

## 🔧 BẠN CẦN TỰ SỬA

### 1. `requirements.txt` — Thêm thư viện Discord
Mở `requirements.txt`, thêm dòng sau vào cuối:
```
discord.py>=2.3.0
```
Sau đó chạy:
```bash
pip install -r requirements.txt
```

### 2. `src/main.py` — Refactor để dùng `core_engine.py`

Hiện tại `main.py` chứa toàn bộ logic khởi tạo (`initializeSystem`, `processQuery`, `loadDeviceConfig`...) và in trực tiếp ra terminal.

**Bạn cần:**
1. Thêm import ở đầu file:
```python
from src.core_engine import initialize_system, run_agent_query
```

2. Thay thế hàm `initializeSystem()` bằng:
```python
def initializeSystem() -> bool:
    return initialize_system()
```

3. Thay thế toàn bộ nội dung hàm `processQuery()` bằng:
```python
def processQuery(query: str, thread_id: str = "default"):
    result = run_agent_query(query, thread_id)

    if not result["success"]:
        print(f"\n\033[91m[LỖI] {result['error']}\033[0m\n")
        return

    # In raw outputs (định dạng cũ)
    raw_outputs = result.get("raw_outputs", {})
    if raw_outputs:
        # ...giữ nguyên đoạn code in khung RAW DATA của bạn...
        pass

    # In phân tích của Analyst (định dạng cũ)
    analysis = result.get("analysis", "")
    if analysis:
        # ...giữ nguyên đoạn code in khung ANALYST của bạn...
        pass
```

Hoặc đơn giản hơn: copy nội dung `run_agent_query` từ `core_engine.py`, bỏ vào `main.py` rồi sửa để nó trả về dict thay vì in ra màn hình.

> 💡 **Gợi ý:** Nếu bạn muốn giữ `main.py` nguyên vẹn (không refactor), bạn vẫn có thể chạy Discord Bot độc lập. Chỉ cần đảm bảo `main.py` và `discord_bot.py` không import lẫn nhau là được.

### 3. `.env` — Tạo từ mẫu
```bash
cp .env.example .env
nano .env
# Sửa DISCORD_BOT_TOKEN và DISCORD_CHANNEL_ID
```

### 4. Chạy thử
```bash
# Terminal 1: Bot Discord
python -m src.discord_bot

# Terminal 2: Giao diện terminal cũ (nếu cần)
python -m src.main
```

---

## 📝 Ghi chú kỹ thuật

- `core_engine.py` dùng **global variables** (`_graph_instance`, `_device_object_instance`) để giữ trạng thái. Cả terminal và Discord đều gọi chung vào đây.
- Discord Bot chạy **async**, nên `run_agent_query` (blocking) được bọc trong `asyncio.to_thread()`.
- Nếu muốn nhiều ngườii dùng Discord cùng lúc, `thread_id` được tạo unique theo `discord_{user_id}_{timestamp}` để tránh xung đột checkpoint.


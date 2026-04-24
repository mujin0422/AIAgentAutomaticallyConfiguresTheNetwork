"""
discord_bot.py — Discord Bot điều khiển Network AI Assistant từ xa
Chạy: python -m src.discord_bot

Yêu cầu: pip install discord.py python-dotenv
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime

# Đảm bảo project root trong PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
import discord
from discord.ext import commands

from src.core_engine import initialize_system, run_agent_query

# Load biến môi trường
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
DISCORD_PREFIX = os.getenv("DISCORD_PREFIX", "!net")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Cấu hình Intents ---
intents = discord.Intents.default()
intents.message_content = True  # BẮT BUỘC: phải bật trong Discord Developer Portal

bot = commands.Bot(command_prefix=DISCORD_PREFIX + " ", intents=intents)
# Lưu ý: prefix là "!net " (có dấu cách) để phân biệt với các lệnh khác


@bot.event
async def on_ready():
    """Khi bot đã kết nối Discord thành công"""
    logger.info(f"Bot đã đăng nhập với tên: {bot.user}")
    logger.info(f"Prefix lệnh: '{DISCORD_PREFIX}'")

    # Khởi tạo hệ thống AI Agent (blocking → chạy trong thread)
    logger.info("Đang khởi tạo Network AI Agent...")
    success = await asyncio.to_thread(initialize_system)

    if success:
        logger.info("[OK] Network AI Agent đã sẵn sàng!")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="mạng GNS3 | !net <lệnh>"
            )
        )
    else:
        logger.error("[FAIL] Khởi tạo Agent thất bại. Kiểm tra GNS3 và config.")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="LỖI KHỞI TẠO — kiểm tra log"
            ),
            status=discord.Status.dnd
        )


@bot.event
async def on_message(message: discord.Message):
    """Xử lý tin nhắn trực tiếp (không cần prefix nếu trong channel đúng)"""
    # Bỏ qua tin nhắn của chính bot
    if message.author == bot.user:
        return

    # Nếu có prefix chuẩn (!net <query>)
    if message.content.startswith(DISCORD_PREFIX + " "):
        await bot.process_commands(message)
        return

    # Nếu KHÔNG có prefix nhưng tin nhắn nằm trong channel được chỉ định
    if DISCORD_CHANNEL_ID:
        try:
            target_channel_id = int(DISCORD_CHANNEL_ID)
            if message.channel.id == target_channel_id:
                # Tự động xử lý như một câu lệnh
                await handle_network_query(message, message.content)
                return
        except ValueError:
            pass

    # Các tin nhắn khác bỏ qua
    await bot.process_commands(message)


async def handle_network_query(message: discord.Message, query: str):
    """
    Chạy agent với câu hỏi và gửi kết quả về Discord.
    Chạy agent trong thread riêng để không block event loop của Discord.
    """
    # Đang typing...
    async with message.channel.typing():
        thread_id = f"discord_{message.author.id}_{int(datetime.now().timestamp())}"

        # Chạy agent (blocking) trong thread
        result = await asyncio.to_thread(run_agent_query, query, thread_id)

    if not result["success"]:
        error_msg = f"❌ **Lỗi:** {result.get('error', 'Không rõ nguyên nhân')}"
        await message.reply(error_msg)
        return

    # --- Định dạng kết quả gửi về Discord ---
    parts = []

    # 1. Phần phân tích của Analyst
    analysis = result.get("analysis", "")
    if analysis:
        parts.append("## Phân tích\n")
        parts.append(analysis)

    # 2. Phần raw output từ thiết bị
    raw_outputs = result.get("raw_outputs", {})
    if raw_outputs:
        parts.append("\n---\n")
        parts.append("## Dữ liệu thô từ thiết bị\n")
        for tool_name, output in raw_outputs.items():
            # Làm sạch output
            display_text = str(output)
            try:
                parsed = json.loads(display_text)
                if isinstance(parsed, dict):
                    if parsed.get("success") is False:
                        display_text = f"Lỗi: {parsed.get('error', 'Không rõ')}"
                    elif "output" in parsed:
                        display_text = str(parsed["output"])
            except Exception:
                pass

            parts.append(f"**`{tool_name}`**")
            parts.append(f"```\n{display_text[:1900]}\n```")

    # Gửi kết quả (cắt nếu quá dài)
    full_response = "\n".join(parts)
    if len(full_response) > 1900:
        # Gửi phần phân tích trước
        if analysis:
            await message.reply(f"## 📊 Phân tích\n{analysis[:1900]}")

        # Gửi raw output riêng, cắt từng phần
        for tool_name, output in raw_outputs.items():
            display_text = str(output)
            try:
                parsed = json.loads(display_text)
                if isinstance(parsed, dict) and "output" in parsed:
                    display_text = str(parsed["output"])
            except Exception:
                pass

            chunk = f"**`{tool_name}`**\n```\n{display_text[:1900]}\n```"
            await message.channel.send(chunk)
    else:
        await message.reply(full_response)


@bot.command(name="net")
async def net_command(ctx: commands.Context, *, query: str):
    """
    Lệnh: !net <câu hỏi>
    Ví dụ: !net show ip interface brief
    """
    await handle_network_query(ctx.message, query)


@bot.command(name="status")
async def status_command(ctx: commands.Context):
    """Lệnh: !net status — Kiểm tra trạng thái hệ thống"""
    from src.core_engine import get_device_info
    device = get_device_info()
    status_msg = (
        "🟢 **Bot đang hoạt động**\n"
        f"• Thiết bị: `{device.hostname if device else 'Chưa cấu hình'}`\n"
        f"• Loại: `{device.device_type if device else 'N/A'}`\n"
        f"• Prefix: `{DISCORD_PREFIX}`\n"
        f"• Channel ID: `{DISCORD_CHANNEL_ID or 'Bất kỳ'}`"
    )
    await ctx.reply(status_msg)


def main():
    if not DISCORD_TOKEN:
        logger.error("Thiếu DISCORD_BOT_TOKEN! Hãy tạo file .env và thêm token.")
        print("\n❌ Lỗi: Không tìm thấy DISCORD_BOT_TOKEN trong .env")
        print("👉 Hướng dẫn: xem docs/discord_setup.md để biết cách lấy token.")
        sys.exit(1)

    logger.info("Khởi động Discord Bot...")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()


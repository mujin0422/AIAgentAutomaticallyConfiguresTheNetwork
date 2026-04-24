"""
core_engine.py — Logic lõi của Network AI Assistant
Tách biệt khởi tạo và chạy agent khỏi giao diện (terminal / discord)
Để dùng: import từ main.py hoặc discord_bot.py
"""

import os
import sys
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.utils.langgraph_fix import *
import yaml
import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from src.graph.workflow import createNetworkAssistantGraph
from src.graph.state import NetworkState, DeviceConnection

# --- CẤU HÌNH ---
GNS3_IP = "172.20.10.3"
GNS3_PORT = "3080"
BASE_URL = f"http://{GNS3_IP}:{GNS3_PORT}/v2"
PROJECT_ID = "cc92102e-89e3-4f2d-8e66-47268c496baa"

os.environ["LANGCHAIN_TRACING"] = "false"
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Global instances ---
_graph_instance = None
_device_object_instance = None


def check_gns3_connectivity() -> bool:
    """Kiểm tra kết nối tới GNS3 Server trước khi khởi động Agent"""
    try:
        response = requests.get(f"{BASE_URL}/version", timeout=5)
        response.raise_for_status()
        version = response.json().get("version")
        logger.info(f"Kết nối GNS3 Server thành công (v{version})")

        proj_resp = requests.get(f"{BASE_URL}/projects/{PROJECT_ID}", timeout=5)
        if proj_resp.status_code == 200:
            logger.info(f"Project '{proj_resp.json().get('name')}' sẵn sàng.")
            return True
        else:
            logger.error(f"Không tìm thấy Project ID: {PROJECT_ID}")
            return False
    except Exception as e:
        logger.error(f"Lỗi kết nối GNS3: {e}")
        return False


def load_device_config():
    try:
        config_path = Path("config/devices.yaml")
        if not config_path.exists():
            return None
        with open(config_path, 'r', encoding='utf-8') as f:
            devices = yaml.safe_load(f)

        if devices:
            first_device_key = list(devices.keys())[0]
            return devices.get(first_device_key)
        return None

    except Exception as e:
        logger.error(f"Lỗi config: {e}")
        return None


def create_device_connection(device_config: dict):
    try:
        return DeviceConnection(
            hostname=str(device_config.get("hostname", "")),
            device_type=str(device_config.get("device_type", "cisco_ios")),
            username=str(device_config.get("username", "")),
            password=str(device_config.get("password", "")),
            secret=str(device_config.get("secret")),
            port=int(device_config.get("port", 22))
        )
    except Exception as e:
        logger.error(f"Lỗi tạo DeviceConnection: {e}")
        return None


def initialize_system() -> bool:
    """
    Khởi tạo toàn bộ hệ thống: kết nối GNS3, load config thiết bị, compile graph.
    Trả về True nếu thành công, False nếu thất bại.
    """
    global _graph_instance, _device_object_instance

    logger.info("[HỆ THỐNG] Bắt đầu khởi tạo ứng dụng...")

    if not check_gns3_connectivity():
        return False

    device_config = load_device_config()
    if not device_config:
        logger.error("Không thể load config thiết bị từ devices.yaml")
        return False

    _device_object_instance = create_device_connection(device_config)

    try:
        _graph_instance = createNetworkAssistantGraph()
        logger.info("Đã khởi tạo LangGraph workflow")
    except Exception as e:
        logger.error(f"Lỗi khởi tạo graph: {e}")
        return False

    logger.info("[HỆ THỐNG] Khởi tạo hoàn tất!")
    return True


def run_agent_query(query: str, thread_id: str = "default") -> Dict[str, Any]:
    """
    Chạy một câu hỏi qua agent graph.
    Không in ra màn hình — chỉ trả về dictionary chứa kết quả.

    Trả về:
    {
        "success": True/False,
        "query": str,
        "raw_outputs": dict,      # Output từ các tool (show commands...)
        "analysis": str,          # Phân tích từ Analyst
        "error": str (nếu có)
    }
    """
    global _graph_instance, _device_object_instance

    if _graph_instance is None:
        return {
            "success": False,
            "query": query,
            "raw_outputs": {},
            "analysis": "",
            "error": "Hệ thống chưa được khởi tạo. Gọi initialize_system() trước."
        }

    initial_state = NetworkState(
        messages=[HumanMessage(content=query)],
        target_device=_device_object_instance,
        devices=[_device_object_instance] if _device_object_instance else []
    )

    config = {"configurable": {"thread_id": thread_id}}

    raw_outputs = {}
    analysis = ""

    try:
        for chunk in _graph_instance.stream(initial_state, config):
            if "extract_data" in chunk:
                raw_outputs = chunk["extract_data"].get("command_outputs", {})

            if "analyst" in chunk:
                msg = chunk["analyst"].get("messages", [])
                if msg:
                    last_msg = msg[-1]
                    if hasattr(last_msg, 'content') and last_msg.content:
                        analysis = last_msg.content

        return {
            "success": True,
            "query": query,
            "raw_outputs": raw_outputs,
            "analysis": analysis,
            "error": ""
        }

    except Exception as e:
        logger.error(f"Lỗi khi chạy agent: {e}", exc_info=True)
        return {
            "success": False,
            "query": query,
            "raw_outputs": raw_outputs,
            "analysis": analysis,
            "error": str(e)
        }


def get_device_info() -> Optional[DeviceConnection]:
    """Trả về thông tin thiết bị đang kết nối (nếu có)"""
    return _device_object_instance


# import os
# import sys
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# sys.path.insert(0, project_root)

# from src.utils.langgraph_fix import *  # Fix LangGraph ImportError + Runtime.server_info
# import yaml
# import requests
# import json
# import logging
# import time
# import textwrap
# from dotenv import load_dotenv
# from pathlib import Path
# from langchain_core.messages import HumanMessage
# from src.graph.workflow import createNetworkAssistantGraph
# from src.graph.state import NetworkState, DeviceConnection

# # --- CONFIGURATION ---
# GNS3_IP = "192.168.2.5"
# GNS3_PORT = "3080"
# BASE_URL = f"http://{GNS3_IP}:{GNS3_PORT}/v2"
# PROJECT_ID = "cc92102e-89e3-4f2d-8e66-47268c496baa"

# os.environ["LANGCHAIN_TRACING"] = "false"
# load_dotenv()

# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s | %(levelname)-8s | %(message)s',
#     datefmt='%H:%M:%S'
# )
# logger = logging.getLogger(__name__)

# graphInstance = None
# deviceObjectInstance = None

# # --- GNS3 HELPER FUNCTIONS ---

# def check_gns3_connectivity() -> bool:
#     """Kiểm tra kết nối tới GNS3 Server trước khi khởi động Agent"""
#     try:
#         response = requests.get(f"{BASE_URL}/version", timeout=5)
#         response.raise_for_status()
#         version = response.json().get("version")
#         logger.info(f"Kết nối GNS3 Server thành công (v{version})")
        
#         proj_resp = requests.get(f"{BASE_URL}/projects/{PROJECT_ID}", timeout=5)
#         if proj_resp.status_code == 200:
#             logger.info(f"Project '{proj_resp.json().get('name')}' sẵn sàng.")
#             return True
#         else:
#             logger.error(f"Không tìm thấy Project ID: {PROJECT_ID}")
#             return False
#     except Exception as e:
#         logger.error(f"Lỗi kết nối GNS3: {e}")
#         return False

# # --- SYSTEM INITIALIZATION ---

# def initializeSystem() -> bool:
#     global graphInstance, deviceObjectInstance
    
#     print("\n\033[92m[HỆ THỐNG] Bắt đầu khởi tạo ứng dụng...\033[0m")
    
#     if not check_gns3_connectivity():
#         return False
    
#     device_config = loadDeviceConfig()
#     if not device_config:
#         logger.error("Không thể load config thiết bị từ devices.yaml")
#         return False
    
#     deviceObjectInstance = createDeviceConnection(device_config)
    
#     try:
#         graphInstance = createNetworkAssistantGraph()
#         logger.info("Đã khởi tạo LangGraph workflow")
#     except Exception as e:
#         logger.error(f"Lỗi khởi tạo graph: {e}")
#         return False
    
#     print("\033[92m[HỆ THỐNG] Khởi tạo hoàn tất!\033[0m\n")
#     return True

# def loadDeviceConfig():
#     try:
#         config_path = Path("config/devices.yaml")
#         if not config_path.exists(): return None
#         with open(config_path, 'r', encoding='utf-8') as f:
#             devices = yaml.safe_load(f)
            
#         if devices:
#             first_device_key = list(devices.keys())[0]
#             return devices.get(first_device_key)
#         return None
        
#     except Exception as e:
#         logger.error(f"Lỗi config: {e}")
#         return None

# def createDeviceConnection(device_config: dict):
#     try:
#         return DeviceConnection(
#             hostname=str(device_config.get("hostname", "")),
#             device_type=str(device_config.get("device_type", "cisco_ios")),
#             username=str(device_config.get("username", "")),
#             password=str(device_config.get("password", "")),
#             secret=str(device_config.get("secret")),
#             port=int(device_config.get("port", 22))
#         )
#     except Exception as e:
#         logger.error(f"Lỗi tạo DeviceConnection: {e}"); return None

# # --- PROCESS & FORMATTING ---

# def processQuery(query: str, thread_id: str = "default"):
#     global graphInstance, deviceObjectInstance
#     if not graphInstance: return
    
#     initial_state = NetworkState(
#         messages=[HumanMessage(content=query)],
#         target_device=deviceObjectInstance,
#         devices=[deviceObjectInstance] if deviceObjectInstance else []
#     )
    
#     config = {"configurable": {"thread_id": thread_id}}
    
#     print("\n\033[92m[HỆ THỐNG] Đang xử lý yêu cầu...\033[0m")
    
#     raw_outputs_to_print = {}

#     for chunk in graphInstance.stream(initial_state, config):
#         if "extract_data" in chunk:
#             raw_outputs_to_print = chunk["extract_data"].get("command_outputs", {})

#         if "analyst" in chunk:
#             # 2. IN KHUNG DỮ LIỆU RAW (NẾU CÓ)
#             if raw_outputs_to_print:
#                 content_width = 120
#                 frame_width = content_width + 4
                
#                 print("\n\t\033[96m" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
                
#                 title = "║ [RAW DATA] KẾT QUẢ THỰC THI TỪ THIẾT BỊ"
#                 print("\t\033[96m" + title + " "*(frame_width - len(title) - 1) + "║\033[0m")
#                 print("\t\033[96m" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")
                
#                 tool_count = len(raw_outputs_to_print)
#                 current_tool = 0
                
#                 for tool_name, result in raw_outputs_to_print.items():
#                     current_tool += 1
#                     display_text = str(result)
#                     try:
#                         parsed_data = json.loads(display_text)
                        
#                         if isinstance(parsed_data, dict):
#                             # 1. Kiểm tra nếu tool báo lỗi
#                             if parsed_data.get("success") is False:
#                                 display_text = f"LỖI: {parsed_data.get('error', 'Không rõ nguyên nhân')}"
#                             # 2. Lấy đích danh trường "output" mà bạn vừa đồng nhất
#                             elif "output" in parsed_data:
#                                 display_text = str(parsed_data["output"])
#                     except Exception:
#                         pass 

#                     # In tên Tool
#                     tool_line = f"Tool đã dùng: {tool_name}"
#                     print("\t\033[96m║ \033[93m" + tool_line.ljust(content_width) + " \033[96m║\033[0m")
#                     print("\t\033[96m║ \033[90m" + "Output:".ljust(content_width) + " \033[96m║\033[0m")
                    
#                     # In từng dòng kết quả (đã làm sạch)
#                     for line in display_text.split('\n'):
#                         # Cắt bỏ ký tự \r thừa và giới hạn độ dài dòng
#                         safe_line = line.replace('\r', '')[:content_width] 
#                         print("\t\033[96m║ \033[90m" + safe_line.ljust(content_width) + " \033[96m║\033[0m")
                    
#                     if current_tool < tool_count:
#                         print("\t\033[96m" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")

#                 print("\t\033[96m" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m\n")

#             # 3. IN KHUNG PHÂN TÍCH CỦA ANALYST (Giữ nguyên cấu trúc cũ)
#             msg = chunk["analyst"].get("messages", [])[-1]
#             if hasattr(msg, 'content') and msg.content:
#                 lines = msg.content.split('\n')
#                 wrapped_lines = []
#                 content_width = 120 
                
#                 for line in lines:
#                     if len(line) > content_width:
#                         wrapped_lines.extend(textwrap.wrap(line, width=content_width, replace_whitespace=False))
#                     else:
#                         wrapped_lines.append(line)
                
#                 frame_width = content_width + 4
#                 print("\033[93m\t" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
#                 title = "║ [ANALYST] PHẢN HỒI"
#                 print("\033[93m\t" + title + " "*(frame_width - len(title) - 1) + "║" + "\033[0m")
                
#                 for line in wrapped_lines:
#                     content_line = "║ " + line.ljust(content_width) + " ║"
#                     print("\t" + content_line)
                    
#                 print("\033[93m\t" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m")

# def interactiveMode():
#     if not initializeSystem():
#         print("\033[91m[LỖI] Khởi tạo thất bại. Vui lòng kiểm tra GNS3 VM và Config.\033[0m")
#         return
    
#     print("\033[92m╔════════════════════════════════════════════════════════════════════════╗\033[0m")
#     print("\033[92m║                          NETWORK AI ASSISTANT                          ║\033[0m")
#     print("\033[92m╠────────────────────────────────────────────────────────────────────────╣\033[0m")
#     print("\033[92m║ - GNS3 Server: Connected (192.168.10.128)                              ║\033[0m")
#     print("\033[92m║ - Enter your request (Enter Q to quit)                                 ║\033[0m")
#     print("\033[92m╚════════════════════════════════════════════════════════════════════════╝\033[0m")
    
#     query_count = 0
#     while True:
#         try:
#             print(f"\n[Phiên làm việc #{query_count + 1}]")
#             query = input("\t\033[93m ➤  Yêu cầu của bạn: \033[0m").strip()
            
#             if query.lower() in ['q', 'exit']: 
#                 print("\033[92m[HỆ THỐNG] Đang thoát... Tạm biệt!\033[0m")
#                 break
#             if not query: continue
            
#             query_count += 1
#             thread_id = f"session_{query_count}_{int(time.time())}"
#             processQuery(query, thread_id=thread_id)
            
#         except KeyboardInterrupt: 
#             print("\n\033[91m[HỆ THỐNG] Đã ngắt bởi người dùng.\033[0m")
#             break

# if __name__ == "__main__":   
#     interactiveMode()

#!/usr/bin/env python3
"""
Network AI Assistant - Giao diện phong cách OpenClaw
Hỗ trợ tiếng Việt, tối giản và chuyên nghiệp
"""

import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.utils.langgraph_fix import *
import yaml
import requests
import json
import logging
import time
import textwrap
from dotenv import load_dotenv
from pathlib import Path
from langchain_core.messages import HumanMessage
from src.graph.workflow import createNetworkAssistantGraph
from src.graph.state import NetworkState, DeviceConnection
from datetime import datetime

# --- Rich imports cho giao diện đẹp ---
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich import box
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, TextColumn

# --- CẤU HÌNH ---
GNS3_IP = "172.20.10.3"
#GNS3_IP = "192.168.2.5"
GNS3_PORT = "3080"
BASE_URL = f"http://{GNS3_IP}:{GNS3_PORT}/v2"
PROJECT_ID = "cc92102e-89e3-4f2d-8e66-47268c496baa"

os.environ["LANGCHAIN_TRACING"] = "false"
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# Rich console
console = Console()

graphInstance = None
deviceObjectInstance = None

# ==================== THÀNH PHẦN GIAO DIỆN ====================

def print_logo():
    """Logo ASCII art phong cách OpenClaw"""
    logo = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     ███╗   ██╗███████╗████████╗██╗    ██╗ ██████╗ ██████╗     ║
    ║     ████╗  ██║██╔════╝╚══██╔══╝██║    ██║██╔═══██╗██╔══██╗    ║
    ║     ██╔██╗ ██║█████╗     ██║   ██║ █╗ ██║██║   ██║██████╔╝    ║
    ║     ██║╚██╗██║██╔══╝     ██║   ██║███╗██║██║   ██║██╔══██╗    ║
    ║     ██║ ╚████║███████╗   ██║   ╚███╔███╔╝╚██████╔╝██║  ██║    ║
    ║     ╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝    ║
    ║                                                               ║
    ║              TRỢ LÝ MẠNG AI - NETWORK ASSISTANT               ║
    ║                Tích hợp GNS3 • AI Cục bộ                      ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(logo, style="cyan")

def print_header():
    """Header đơn giản với thông tin phiên bản"""
    version_text = Text()
    version_text.append("Trợ lý Mạng AI ", style="bold cyan")
    version_text.append("v1.0", style="dim")
    version_text.append(" - Tự động hóa mạng với AI cục bộ!", style="italic dim")
    console.print(Align.center(version_text))
    console.print()

def print_warning():
    """Khung cảnh báo bảo mật (phong cách OpenClaw)"""
    warning_text = (
        "[bold yellow]⚠️ CẢNH BÁO BẢO MẬT - Vui lòng đọc kỹ[/bold yellow]\n\n"
        "Trợ lý này có thể thực thi lệnh trên thiết bị mạng.\n"
        "Một câu lệnh độc hại có thể kích hoạt các thao tác không an toàn.\n\n"
        "[dim]Khuyến nghị cơ bản:[/dim]\n"
        "• Luôn kiểm tra lệnh trước khi thực thi\n"
        "• Sử dụng tài khoản chỉ đọc khi có thể\n"
        "• Cách ly GNS3 khỏi mạng sản xuất\n"
        "• Không expose công cụ này ra internet"
    )
    
    warning_box = Panel(
        warning_text,
        border_style="yellow",
        box=box.HEAVY,
        padding=(1, 2)
    )
    console.print(warning_box)
    console.print()

def print_status():
    """Khung trạng thái hệ thống"""
    try:
        # Kiểm tra kết nối GNS3
        response = requests.get(f"{BASE_URL}/version", timeout=3)
        gns3_status = "[green]● Đã kết nối[/green]" if response.status_code == 200 else "[red]● Mất kết nối[/red]"
        gns3_version = response.json().get("version", "unknown") if response.status_code == 200 else "N/A"
    except:
        gns3_status = "[red]● Mất kết nối[/red]"
        gns3_version = "N/A"
    
    device_hostname = deviceObjectInstance.hostname if deviceObjectInstance else "[yellow]Chưa cấu hình[/yellow]"
    
    status_text = (
        f"[cyan]├─[/cyan] Máy chủ GNS3:    {GNS3_IP}:{GNS3_PORT} {gns3_status}\n"
        f"[cyan]├─[/cyan] Phiên bản:      {gns3_version}\n"
        f"[cyan]├─[/cyan] Dự án:          {PROJECT_ID[:16]}...\n"
        f"[cyan]├─[/cyan] Thiết bị:       {device_hostname}\n"
        f"[cyan]└─[/cyan] Mô hình AI:     Cục bộ (Ollama/Qwen)"
    )
    
    console.print(Panel(status_text, border_style="dim", padding=(0, 1)))
    console.print()

def print_commands():
    """Khung hiển thị lệnh điều khiển"""
    commands_text = (
        "[cyan]/help[/cyan]     - Hiển thị trợ giúp\n"
        "[cyan]/clear[/cyan]    - Xóa màn hình\n"
        "[cyan]/status[/cyan]   - Kiểm tra trạng thái\n"
        "[cyan]/exit[/cyan]     - Thoát chương trình"
    )
    console.print(Panel(commands_text, title="[bold]Lệnh điều khiển[/bold]", border_style="dim", padding=(0, 1)))
    console.print()

def print_help():
    """Trợ giúp chi tiết"""
    help_text = (
        "[bold cyan]Trợ Lý Mạng AI - Hướng dẫn sử dụng[/bold cyan]\n\n"
        "Bạn có thể yêu cầu tôi thực hiện các thao tác mạng như:\n\n"
        "    • [yellow]Hiển thị thông tin[/yellow]      - \"show version\", \"show running-config\"\n"
        "    • [yellow]Kiểm tra cổng mạng[/yellow]      - \"show ip interface brief\"\n"
        "    • [yellow]Bảng định tuyến[/yellow]         - \"show ip route\"\n"
        "    • [yellow]Chẩn đoán mạng[/yellow]          - \"ping 8.8.8.8\", \"traceroute\"\n"
        "    • [yellow]Cấu hình[/yellow]                - \"show running-config interface gi0/0\"\n\n"
        "[dim]Lưu ý: Các lệnh được thực thi trên thiết bị mạng đã cấu hình thông qua GNS3.[/dim]"
    )
    console.print(Panel(help_text, border_style="cyan", padding=(1, 2)))
    console.print()

# ==================== HÀM HỖ TRỢ GNS3 ====================

def check_gns3_connectivity() -> bool:
    """Kiểm tra kết nối tới GNS3 Server"""
    try:
        response = requests.get(f"{BASE_URL}/version", timeout=5)
        response.raise_for_status()
        version = response.json().get("version")
        logger.info(f"Đã kết nối GNS3 Server (v{version})")
        
        proj_resp = requests.get(f"{BASE_URL}/projects/{PROJECT_ID}", timeout=5)
        if proj_resp.status_code == 200:
            logger.info(f"Dự án sẵn sàng: {proj_resp.json().get('name')}")
            return True
        else:
            logger.error(f"Không tìm thấy dự án: {PROJECT_ID}")
            return False
    except Exception as e:
        logger.error(f"Kết nối GNS3 thất bại: {e}")
        return False

def initializeSystem() -> bool:
    global graphInstance, deviceObjectInstance
    
    console.print("\n[cyan]Đang khởi tạo hệ thống...[/cyan]")
    
    if not check_gns3_connectivity():
        console.print("[red]✗ Kết nối GNS3 thất bại[/red]")
        return False
    
    device_config = loadDeviceConfig()
    if not device_config:
        console.print("[red]✗ Không tìm thấy cấu hình thiết bị[/red]")
        return False
    
    deviceObjectInstance = createDeviceConnection(device_config)
    
    try:
        graphInstance = createNetworkAssistantGraph()
        console.print("[green]✓ Hệ thống sẵn sàng[/green]\n")
        return True
    except Exception as e:
        logger.error(f"Khởi tạo graph thất bại: {e}")
        return False

def loadDeviceConfig():
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
        logger.error(f"Lỗi đọc config: {e}")
        return None

def createDeviceConnection(device_config: dict):
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
        logger.error(f"Lỗi tạo kết nối thiết bị: {e}")
        return None

# ==================== ĐỊNH DẠNG ĐẦU RA ====================

def display_raw_data(tool_outputs: dict):
    """Hiển thị dữ liệu thô từ thiết bị (phong cách tối giản)"""
    if not tool_outputs:
        return
    
    console.print("\n[dim]─── KẾT QUẢ THÔ TỪ THIẾT BỊ ───[/dim]")
    
    for tool_name, result in tool_outputs.items():
        display_text = str(result)
        try:
            parsed_data = json.loads(display_text)
            if isinstance(parsed_data, dict):
                if parsed_data.get("success") is False:
                    display_text = f"[red]Lỗi: {parsed_data.get('error', 'Không rõ nguyên nhân')}[/red]"
                elif "output" in parsed_data:
                    display_text = str(parsed_data["output"])
        except:
            pass
        
        console.print(f"\n[cyan]› {tool_name}[/cyan]")
        console.print(display_text)
    
    console.print("[dim]─────────────────────────────────[/dim]\n")

def display_analysis(content: str):
    """Hiển thị phân tích từ AI với định dạng sạch"""
    # Xuống dòng dài
    lines = content.split('\n')
    wrapped_lines = []
    for line in lines:
        if len(line) > 100:
            wrapped_lines.extend(textwrap.wrap(line, width=100))
        else:
            wrapped_lines.append(line)
    
    wrapped_content = '\n'.join(wrapped_lines)
    
    console.print(Panel(
        wrapped_content,
        border_style="green",
        padding=(1, 2)
    ))
    console.print()

def processQuery(query: str, thread_id: str = "default"):
    global graphInstance, deviceObjectInstance
    if not graphInstance: 
        return
    
    initial_state = NetworkState(
        messages=[HumanMessage(content=query)],
        target_device=deviceObjectInstance,
        devices=[deviceObjectInstance] if deviceObjectInstance else []
    )
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Hiển thị spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Đang xử lý...[/cyan]", total=None)
        
        raw_outputs_to_print = {}
        
        for chunk in graphInstance.stream(initial_state, config):
            if "extract_data" in chunk:
                raw_outputs_to_print = chunk["extract_data"].get("command_outputs", {})
            
            if "analyst" in chunk:
                msg = chunk["analyst"].get("messages", [])[-1]
                if hasattr(msg, 'content') and msg.content:
                    if raw_outputs_to_print:
                        display_raw_data(raw_outputs_to_print)
                    display_analysis(msg.content)
        
        progress.update(task, completed=True)

# ==================== CHẠY CHÍNH ====================

def interactiveMode():
    console.clear()
    print_logo()
    print_header()
    print_warning()
    
    if not initializeSystem():
        console.print("[red]Khởi tạo thất bại. Kiểm tra GNS3 và cấu hình.[/red]")
        return
    
    print_status()
    print_commands()
    
    session_count = 0
    
    while True:
        try:
            # Ô nhập lệnh đơn giản
            user_input = Prompt.ask("\n[bold cyan]┌─[/bold cyan] [white]trợ-lý-mạng[/white] [bold cyan]─┐[/bold cyan]\n[bold cyan]└─>[/bold cyan]")
            
            if not user_input:
                continue
            
            cmd = user_input.lower().strip()
            
            if cmd in ['/exit', 'exit', 'q', 'thoát']:
                console.print("\n[yellow]Tạm biệt! Hẹn gặp lại![/yellow]\n")
                break
            elif cmd == '/clear':
                console.clear()
                print_logo()
                print_header()
                print_status()
                print_commands()
                continue
            elif cmd == '/help':
                print_help()
                continue
            elif cmd == '/status':
                print_status()
                continue
            
            # Xử lý câu hỏi bình thường
            session_count += 1
            thread_id = f"session_{session_count}_{int(time.time())}"
            
            # Hiển thị câu hỏi của người dùng
            console.print(f"\n[dim]› {user_input}[/dim]\n")
            
            processQuery(user_input, thread_id=thread_id)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Đã dừng bởi người dùng[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/red]")
            logger.error(f"Lỗi không mong muốn: {e}", exc_info=True)

if __name__ == "__main__":
    interactiveMode()
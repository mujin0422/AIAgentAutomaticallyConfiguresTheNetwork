import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
from langchain_core.messages import HumanMessage
from src.graph.workflow import create_network_assistant_graph
from src.graph.state import NetworkState, DeviceConnection
import logging
import time
import textwrap

# Disable LangSmith & Load environment variables
os.environ["LANGCHAIN_TRACING"] = "false"
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def load_device_config(device_name: str = None):
    """Load device configuration - LUÔN LẤY DEFAULT"""
    try:
        config_path = Path("config/devices.yaml")
        if not config_path.exists():
            logger.warning("Không tìm thấy file config/devices.yaml")
            return None
            
        with open(config_path, 'r', encoding='utf-8') as f:
            devices = yaml.safe_load(f)
        
        return devices.get("default")
            
    except Exception as e:
        logger.error(f"Lỗi đọc file config: {e}")
        return None
    
def test_ssh_connection(device_config: dict) -> bool:
    """Kiểm tra kết nối SSH trước khi chạy"""
    try:
        from netmiko import ConnectHandler
        
        device = {
            'device_type': device_config.get('device_type', 'cisco_ios'),
            'host': device_config.get('hostname'),
            'username': device_config.get('username'),
            'password': device_config.get('password'),
            'secret': device_config.get('secret'),
            'port': device_config.get('port', 22),
            'conn_timeout': 10,
        }
        
        connection = ConnectHandler(**device)
        connection.disconnect()
        logger.info("SSH connection test successful")
        return True
        
    except Exception as e:
        logger.error(f"SSH connection test failed: {e}")
        return False
    
def create_device_connection(device_config: dict):
    """Tạo DeviceConnection object từ config dict"""
    if not device_config:
        return None
        
    try:
        device_obj = DeviceConnection(
            hostname=str(device_config.get("hostname", "")),
            device_type=str(device_config.get("device_type", "cisco_ios")),
            username=str(device_config.get("username", "")),
            password=str(device_config.get("password", "")),
            secret=str(device_config.get("secret")),
            port=int(device_config.get("port", 22))
        )
        logger.info(f"Đã tạo kết nối đến thiết bị: {device_obj.hostname}")
        return device_obj
        
    except Exception as e:
        logger.error(f"Lỗi tạo DeviceConnection: {e}")
        return None

def process_query(query: str, device_name: str = None, thread_id: str = "default"):
    """Xử lý yêu cầu của người dùng"""
    start_time = time.time()
    print("\n\033[91m[HỆ THỐNG] Bắt đầu khởi tạo ...\033[0m")
    logger.info(f"Tiếp nhận yêu cầu: {query[:255]}...")
    
    try:
        # 1.Load & Validate cấu hình (Load device config & test SSH connection)
        device_config = load_device_config(device_name)

        if not device_config:
            print("Không tìm thấy cấu hình thiết bị. Vui lòng kiểm tra config/devices.yaml")
            return None

        if not test_ssh_connection(device_config):
            print("Không thể kết nối SSH đến thiết bị. Vui lòng kiểm tra mạng và thông tin đăng nhập.")
            return None
        
        # 2. Khởi tạo Graph và State (Load graph) 
        logger.info("Đang khởi tạo graph...")
        graph = create_network_assistant_graph()
        device_obj = create_device_connection(device_config) 
        
        logger.info("Đang tạo initial state với yêu cầu và thiết bị ...")
        initial_state = NetworkState(
            messages=[HumanMessage(content=query)],
            target_device=device_obj,
            devices=[device_obj] if device_obj else []
        )
        
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # 3. Chạy workflow với Streaming 
        logger.info("Đang chạy LangGraph workflow...")
        invoke_start = time.time()

        print("\n\033[91m[HỆ THỐNG] Bắt đầu xử lý ...\033[0m")
        # Streaming để theo dõi tiến trình của từng Agent
        for chunk in graph.stream(initial_state, config):
            # In kết quả từ Analyst ngay khi có (Streaming output)
            if "analyst" in chunk:
                messages = chunk["analyst"].get("messages", [])
                for msg in messages:
                    if hasattr(msg, 'content') and msg.content:
                        lines = msg.content.split('\n')
                        wrapped_lines = []
                        content_width = 198
                        for line in lines:
                            if len(line) > content_width:
                                wrapped_lines.extend(textwrap.wrap(line, width=content_width, replace_whitespace=False))
                            else:
                                wrapped_lines.append(line)
                        
                        # Frame the response
                        frame_width = content_width + 4
                        print("\033[93m\t" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
                        title = "║ [ANALYST] phản hồi"
                        print("\033[93m\t" + title + " "*(frame_width - len(title) - 1) + "║" + "\033[0m")
                        for line in wrapped_lines:
                            content_line = "║ " + line.ljust(content_width) + " ║"
                            print("\t" + content_line)
                        print("\033[93m\t" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m")

        invoke_time = time.time() - invoke_start
        logger.info(f"Workflow hoàn thành trong {invoke_time:.2f}s")
        
        # 4. Lấy State cuối cùng từ Checkpointer để in Báo cáo Tổng hợp
        # Cách này đảm bảo lấy được dữ liệu chính xác nhất sau khi qua node 'after_analyst'
        snapshot = graph.get_state(config)
        final_state_data = snapshot.values
        
        if final_state_data.get("final_report"):
            logger.info("Đã tạo báo cáo thành công")
            report = final_state_data["final_report"]
            lines = report.split("\n")
            wrapped_lines = []
            content_width = 198
            for line in lines:
                if len(line) > content_width:
                    wrapped_lines.extend(textwrap.wrap(line, width=content_width, replace_whitespace=False))
                else:
                    wrapped_lines.append(line)

            frame_width = content_width + 4
            print("\033[1m\033[92m\t" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
            title = "║ TỔNG HỢP BÁO CÁO CUỐI CÙNG"
            print("\033[1m\033[92m\t" + title + " "*(frame_width - len(title) - 1) + "║" + "\033[0m")
            print("\033[1m\033[92m\t" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")
            for line in wrapped_lines:
                content_line = "║ " + line.ljust(content_width) + " ║"
                print("\t" + content_line)
            print("\033[1m\033[92m\t" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m")
        else:
            logger.warning("Không tìm thấy trường final_report trong state")
            messages = final_state_data.get("messages", [])
            if messages:
                print(f"\n\033[93mKết quả cuối cùng:\033[0m {messages[-1].content}")
        
        print(f"\033[91m\n[HỆ THỐNG] trạng thái: {final_state_data.get('current_phase', 'N/A')}\033[0m")
        
        total_time = time.time() - start_time
        logger.info(f"Tổng thời gian xử lý: {total_time:.2f}s\n\n")
        
        return final_state_data
        
    except Exception as e:
        logger.error(f"Lỗi xử lý: {e}", exc_info=True)
        print(f"❌ Đã xảy ra lỗi: {e}")
        return None

def interactive_mode():
    """Chạy interactive mode"""
    print("\033[91m╔════════════════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[91m║ NETWORK AI ASSISTANT                                                   ║\033[0m")
    print("\033[91m╠────────────────────────────────────────────────────────────────────────╣\033[0m")
    print("\033[91m║ - Enter your request (Enter Q to quit)                                 ║\033[0m")
    print("\033[91m╚════════════════════════════════════════════════════════════════════════╝\033[0m")
    
    thread_id = f"session_{os.getpid()}"
    
    while True:
        try:
            query = input("\t\033[92m ➤  Yêu cầu của bạn: \033[0m").strip()
            if query.lower() in ['q', 'Q']:
                print("\t\033[92m ➤  Tạm biệt!\033[0m")
                break
            
            if not query:
                continue
            
            process_query(query, thread_id=thread_id)
            
        except KeyboardInterrupt:
            print("\t\033[92m ➤  Tạm biệt!\033[0m")
            break
        except Exception as e:
            logger.error(f"Lỗi: {str(e)}", exc_info=True)
            print(f"Đã xảy ra lỗi: {str(e)}")

if __name__ == "__main__":   
    interactive_mode()

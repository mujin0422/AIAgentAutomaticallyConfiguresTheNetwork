import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
from langchain_core.messages import HumanMessage
from src.graph.workflow import createNetworkAssistantGraph
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

# Biến toàn cục để tái sử dụng
graphInstance = None
deviceObjectInstance = None

def initializeSystem() -> bool:
    """Khởi tạo hệ thống 1 lần duy nhất khi start"""
    global graphInstance, deviceObjectInstance
    
    print("\n\033[92m[HỆ THỐNG] Bắt đầu khởi tạo ứng dụng...\033[0m")
    startup_time = time.time()
    
    # 1. Load config
    device_config = loadDeviceConfig()
    if not device_config:
        logger.error("Không thể load config thiết bị")
        return False
    
    # 2. Tạo DeviceConnection object
    deviceObjectInstance = createDeviceConnection(device_config)
    if not deviceObjectInstance:
        logger.error("Không thể tạo DeviceConnection object")
        return False
    
    # 3. Khởi tạo Graph
    try:
        graphInstance = createNetworkAssistantGraph()
        logger.info("Đã khởi tạo LangGraph workflow")
    except Exception as e:
        logger.error(f"Lỗi khởi tạo graph: {e}")
        return False
    
    startup_time = time.time() - startup_time
    print(f"\033[92m[HỆ THỐNG] Khởi tạo hoàn tất trong {startup_time:.2f}s\033[0m\n")
    return True

def loadDeviceConfig(device_name: str = None):
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

def createDeviceConnection(device_config: dict):
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

def processQuery(query: str, thread_id: str = "default"):
    """Xử lý yêu cầu của người dùng - KHÔNG khởi tạo lại gì cả"""
    global graphInstance, deviceObjectInstance
    
    # Kiểm tra hệ thống đã khởi tạo chưa
    if not graphInstance or not deviceObjectInstance:
        print("Hệ thống chưa được khởi tạo. Vui lòng khởi động lại.")
        return None
    
    start_time = time.time()
    logger.info(f"Xử lý query: {query[:100]}...")
    
    try:
        # Tạo state mới cho mỗi query
        initial_state = NetworkState(
            messages=[HumanMessage(content=query)],
            target_device=deviceObjectInstance,
            devices=[deviceObjectInstance] if deviceObjectInstance else []
        )
        
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Chạy workflow (dùng graph đã khởi tạo sẵn)
        print("\n\033[92m[HỆ THỐNG] Đang xử lý yêu cầu...\033[0m")
        invoke_start = time.time()
        
        # Streaming output
        for chunk in graphInstance.stream(initial_state, config):
            if "analyst" in chunk:
                messages = chunk["analyst"].get("messages", [])
                for msg in messages:
                    if hasattr(msg, 'content') and msg.content:
                        # Format output
                        lines = msg.content.split('\n')
                        wrapped_lines = []
                        content_width = 148
                        for line in lines:
                            if len(line) > content_width:
                                wrapped_lines.extend(textwrap.wrap(line, width=content_width, replace_whitespace=False))
                            else:
                                wrapped_lines.append(line)
                        
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
        
        # Lấy kết quả cuối cùng
        snapshot = graphInstance.get_state(config)
        final_state_data = snapshot.values
        
        # In báo cáo tổng hợp
        if final_state_data.get("final_report"):
            report = final_state_data["final_report"]
            lines = report.split("\n")
            wrapped_lines = []
            content_width = 148
            for line in lines:
                if len(line) > content_width:
                    wrapped_lines.extend(textwrap.wrap(line, width=content_width, replace_whitespace=False))
                else:
                    wrapped_lines.append(line)
            
            frame_width = content_width + 4
            print("\033[1m\033[93m\t" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
            title = "║ TỔNG HỢP BÁO CÁO"
            print("\033[1m\033[93m\t" + title + " "*(frame_width - len(title) - 1) + "║" + "\033[0m")
            print("\033[1m\033[93m\t" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")
            for line in wrapped_lines:
                content_line = "║ " + line.ljust(content_width) + " ║"
                print("\t" + content_line)
            print("\033[1m\033[93m\t" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m")
        
        print(f"\033[92m\n[HỆ THỐNG] Trạng thái: {final_state_data.get('current_phase', 'N/A')}\033[0m")
        
        total_time = time.time() - start_time
        logger.info(f"Tổng thời gian xử lý: {total_time:.2f}s\n")
        
        return final_state_data
        
    except Exception as e:
        logger.error(f"Lỗi xử lý: {e}", exc_info=True)
        print(f"Đã xảy ra lỗi: {e}")
        return None

def interactiveMode():
    """Chạy interactive mode"""
    # Khởi tạo hệ thống 1 lần duy nhất
    if not initializeSystem():
        print("Không thể khởi tạo hệ thống. Vui lòng kiểm tra:")
        print("1. File config/devices.yaml có tồn tại và đúng định dạng")
        print("2. Thông tin SSH (hostname, username, password) chính xác")
        print("3. Thiết bị có thể kết nối được qua mạng")
        return
    
    print("\033[92m╔════════════════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[92m║ NETWORK AI ASSISTANT                                                   ║\033[0m")
    print("\033[92m╠────────────────────────────────────────────────────────────────────────╣\033[0m")
    print("\033[92m║ - Enter your request (Enter Q to quit)                                 ║\033[0m")
    print("\033[92m║ - Graph và SSH connection đã được khởi tạo sẵn                         ║\033[0m")
    print("\033[92m╚════════════════════════════════════════════════════════════════════════╝\033[0m")
    
    query_count = 0
    
    while True:
        try:
            query = input("\t\033[93m ➤  Yêu cầu của bạn: \033[0m").strip()
            if query.lower() in ['q', 'Q']:
                print("\t\033[93m ➤  Tạm biệt!\033[0m")
                break
            
            if not query:
                continue
            
            query_count += 1
            # ✅ QUAN TRỌNG: Tạo thread_id MỚI cho mỗi query
            thread_id = f"session_{query_count}_{int(time.time() * 1000)}"
            logger.info(f"Query #{query_count} - Thread: {thread_id}")
            processQuery(query, thread_id=thread_id)
            
        except KeyboardInterrupt:
            print("\t\033[93m ➤  Tạm biệt!\033[0m")
            break
        except Exception as e:
            logger.error(f"Lỗi: {str(e)}", exc_info=True)
            print(f"Đã xảy ra lỗi: {str(e)}")

if __name__ == "__main__":   
    interactiveMode()
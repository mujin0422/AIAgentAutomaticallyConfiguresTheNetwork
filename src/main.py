import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
from langchain_core.messages import HumanMessage
from src.graph.workflow import create_network_assistant_graph
from src.graph.state import NetworkState, DeviceConnection
import logging
import time

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

def process_query(query: str, device_name: str = None, thread_id: str = "default"):
    """Xử lý câu hỏi của người dùng"""
    start_time = time.time()
    logger.info(f"Bắt đầu xử lý câu hỏi: {query[:255]}...")
    
    try:
        # Load device config -> Lấy cấu hình thiết bị từ file config (Hiện tại luôn lấy default)
        device_config = load_device_config(device_name)
        if not device_config:
            logger.error("Không có cấu hình thiết bị")
            print("Không tìm thấy cấu hình thiết bị. Vui lòng kiểm tra config/devices.yaml")
            return None
        
        # Test SSH connection -> Đảm bảo thiết bị có thể truy cập được trước khi chạy workflow
        if not test_ssh_connection(device_config):
            print("Không thể kết nối SSH đến thiết bị. Vui lòng kiểm tra mạng và thông tin đăng nhập.")
            return None
        
        # Load graph -> Tạo đồ thị xử lý với các agent (supervisor, network_expert, analyst)
        logger.info("Đang khởi tạo graph...")
        graph = create_network_assistant_graph()
        
        # Create device connection object -> Chuyển config dict thành Pydantic model DeviceConnection
        device_obj = create_device_connection(device_config) 
        
        # Create initial state
        logger.info("Đang tạo initial state...")
        initial_state = NetworkState(
            messages=[HumanMessage(content=query)],
            target_device=device_obj,
            devices=[device_obj] if device_obj else [] ###
        )
        
        # Configure thread -> Dùng để lưu trạng thái (state) giữa các lần chạy (Cho phép theo dõi và quản lý nhiều phiên làm việc song song nếu cần)
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Run graph with streaming -> Thực thi workflow với state ban đầu và cấu hình đã thiết lập
        logger.info("Đang chạy LangGraph workflow...")
        invoke_start = time.time()

        print("\nĐang xử lý...\n")
        # Cách 1: Không streaming (chờ đến khi hoàn thành mới có kết quả) -> KHÔNG PHÙ HỢP CHO TÁC VỤ PHÂN TÍCH MẠNG, NÊN SỬ DỤNG STREAMING
        # final_state = graph.invoke(initial_state, config)
        # for chunk in graph.stream(initial_state, config):
        #     print(chunk, end="", flush=True)
        # final_state = None  # Streaming không trả về final state trực tiếp !!!!! -> lỗi  

        # Cách 2: Streaming (nhận kết quả từng phần trong quá trình xử lý) -> PHÙ HỢP CHO TÁC VỤ PHÂN TÍCH MẠNG, CHO PHÉP XEM KẾT QUẢ PHÂN TÍCH NGAY KHI CÓ
        # final_state = None
        # for chunk in graph.stream(initial_state, config):
        #     print(chunk, end="", flush=True)
        #     final_state = chunk  # Lưu chunk cuối cùng

        # Cách 3: Streaming với kiểm tra kết quả phân tích (analyst) -> PHÙ HỢP CHO TÁC VỤ PHÂN TÍCH MẠNG, CHO PHÉP XEM KẾT QUẢ PHÂN TÍCH NGAY KHI CÓ VÀ IN RA ĐỊNH DẠNG RÕ RÀNG
        final_state = None
        for chunk in graph.stream(initial_state, config):
            # Kiểm tra nếu có analyst (kết quả phân tích)
            if "analyst" in chunk:
                messages = chunk["analyst"].get("messages", [])
                for msg in messages:
                    if hasattr(msg, 'content') and msg.content:
                        # In kết quả phân tích
                        print("\n" + "="*100)
                        print(" KẾT QUẢ:")
                        print("-"*100)
                        print(msg.content)
                        print("="*100)
            final_state = chunk

        invoke_time = time.time() - invoke_start
        logger.info(f"Workflow hoàn thành trong {invoke_time:.2f}s")
        
        # Log results -> Hiển thị kết quả cuối cùng (báo cáo hoặc trạng thái hiện tại) sau khi workflow kết thúc
        if final_state and final_state.get("final_report"):
            logger.info("📄 Đã tạo báo cáo")
            print("\n" + "="*80)
            print(final_state["final_report"])
            print("="*80 + "\n")
        else:
            logger.warning("Không có báo cáo")
            print(f"\nTrạng thái: {final_state.get('current_phase', 'N/A')}")
            if final_state:
                print(f"\nTrạng thái: {final_state.get('current_phase', 'N/A')}")
                if final_state.get("analysis_results"):
                    print(f"Kết quả phân tích: {final_state.get('analysis_results')}")
        
        
        total_time = time.time() - start_time
        logger.info(f"Tổng thời gian xử lý: {total_time:.2f}s")
        
        return final_state
        
    except Exception as e:
        logger.error(f"Lỗi xử lý: {e}", exc_info=True)
        print(f"Đã xảy ra lỗi: {e}")
        return None

def interactive_mode():
    """Chạy interactive mode"""
    print("||======================================================||")
    print("|| NETWORK AI ASSISTANT - HỖ TRỢ XỬ LÝ SỰ CỐ MẠNG       ||")
    print("||------------------------------------------------------||")
    print("|| - Nhập câu hỏi của bạn                               ||")
    print("||======================================================||")
    
    thread_id = f"session_{os.getpid()}"
    
    while True:
        try:
            query = input("\n- Enter your question (Enter Q to quit): ").strip()
            
            if query.lower() in ['q', 'Q']:
                print("\n\nTạm biệt!")
                break
            
            if not query:
                continue
            
            process_query(query, thread_id=thread_id)
            
        except KeyboardInterrupt:
            print("\n\nTạm biệt!")
            break
        except Exception as e:
            logger.error(f"Lỗi: {str(e)}", exc_info=True)
            print(f"Đã xảy ra lỗi: {str(e)}")

if __name__ == "__main__":   
    interactive_mode()

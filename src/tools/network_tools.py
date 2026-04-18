import os
import re
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
import yaml
from src.tools.parser_tools import *

def get_ssh_params():
    """Lấy tham số SSH từ môi trường"""
    return {
        'conn_timeout': int(os.getenv('SSH_TIMEOUT', 60)),
        'auth_timeout': int(os.getenv('SSH_AUTH_TIMEOUT', 30)),
        'global_delay_factor': float(os.getenv('SSH_DELAY_FACTOR', 2)),
    }

def get_device_config(device_identifier: str):
    """
    Đọc config thiết bị từ file yaml dựa vào tên (VD: 'P1') hoặc IP (VD: '10.0.0.1').
    """
    try:
        with open("config/devices.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # Nếu truyền vào tên (P1, PE1...)
            if device_identifier in config:
                return config[device_identifier]
                
            # Nếu truyền vào địa chỉ IP
            for key, val in config.items():
                if val.get("hostname") == device_identifier:
                    return val
                    
            return None # Không tìm thấy
    except Exception as e:
        print(f"Lỗi đọc config: {e}")
        return None

def connect_to_device(target: str) -> Dict[str, Any]:
    device_cfg = get_device_config(target)
    if not device_cfg:
        return {"success": False, "error": f"Không tìm thấy cấu hình cho '{target}'"}
    
    # Đã sửa lỗi ghi đè biến ở đây
    target_host = str(device_cfg.get("hostname", ""))
    username = str(device_cfg.get("username", ""))
    password = str(device_cfg.get("password", ""))
    secret = str(device_cfg.get("secret", ""))
    port = int(device_cfg.get("port", 22))
    
    connection_params = {
        'device_type': str(device_cfg.get("device_type", "cisco_ios")), 
        'host': target_host,
        'username': username,
        'password': password,
        'secret': secret,
        'port': port,
        'session_timeout': 15,
        'fast_cli': False,
        **get_ssh_params()
    }
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret and not connection.check_enable_mode():
            connection.enable()
        return {"success": True, "connection": connection}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def get_interface_ip(hostname: str) -> Dict[str, Any]:
    """
    LẤY ĐỊA CHỈ IP TRÊN TẤT CẢ CÁC INTERFACE CỦA MỘT THIẾT BỊ CỤ THỂ.
    Sử dụng lệnh 'show ip interface brief'. (VD: hostname="P1").
    """
    try:
        # Gọi thẳng hàm Python, KHÔNG dùng .invoke()
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]: return conn_res

        connection = conn_res["connection"]
        output = connection.send_command_timing("show ip interface brief")
        connection.disconnect() # Ngắt kết nối ngay lập tức
        
        # Dùng hàm parse từ parser_tools của bạn (nếu có lỗi đoạn này thì cứ trả về output thô)
        try:
            interfaces = parse_interface_ip(output)
        except Exception:
            interfaces = {}
               
        return {"success": True, "device": hostname, "interfaces": interfaces, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def ping_test(target_ip: str, source_hostname: str) -> Dict[str, Any]:
    """
    THỰC HIỆN LỆNH PING TỪ MỘT THIẾT BỊ NGUỒN ĐẾN IP ĐÍCH.
    Args:
        target_ip: IP cần ping đến (VD: "10.0.0.2").
        source_hostname: Thiết bị thực hiện lệnh ping (VD: "P1").
    """
    try:
        # Gọi thẳng hàm Python, KHÔNG dùng .invoke()
        conn_res = connect_to_device(source_hostname)
        if not conn_res["success"]: return conn_res

        connection = conn_res["connection"]
        
        # Với lệnh ping, có thể tốn thời gian chờ gói tin phản hồi, 
        # nên dùng send_command với read_timeout cao sẽ an toàn hơn.
        ping_output = connection.send_command(f"ping {target_ip}", read_timeout=60)
        connection.disconnect() # Ngắt kết nối
        
        success_rate = 0
        match = re.search(r"Success rate is (\d+) percent", ping_output)
        if match: 
            success_rate = int(match.group(1))
        
        return {
            "success": True, 
            "source": source_hostname, 
            "target": target_ip, 
            "success_rate": success_rate, 
            "output": ping_output
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def get_routing_table(hostname: str) -> Dict[str, Any]:
    """LẤY BẢNG ĐỊNH TUYẾN CỦA ROUTER CỤ THỂ (VD: hostname="P1")."""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]: return conn_res

        connection = conn_res["connection"]
        routing_table = connection.send_command_timing("show ip route")
        connection.disconnect() # Lấy xong là phải ngắt kết nối ngay
        return {"success": True, "device": hostname, "output": routing_table}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def execute_show_command(command: str, hostname: str) -> Dict[str, Any]:
    """THỰC THI LỆNH SHOW BẤT KỲ TRÊN THIẾT BỊ CHỈ ĐỊNH (VD: command="show ip ospf neighbor", hostname="P1")."""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]: return conn_res

        connection = conn_res["connection"]
        output = connection.send_command_timing(command, strip_prompt=False, strip_command=False)
        connection.disconnect()
        return {"success": True, "device": hostname, "command": command, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}
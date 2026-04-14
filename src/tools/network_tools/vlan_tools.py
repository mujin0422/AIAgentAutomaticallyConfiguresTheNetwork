from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from src.tools.network_tools import get_default_device_config, get_ssh_params
from src.tools.parser_tools import parse_vlan_output
# from src.tools.parser_tools import *

@tool
def check_vlan_status(device_info: Optional[Dict[str, Any]] = None, vlan_id: int = 0) -> Dict[str, Any]:
    """
    KIỂM TRA TRẠNG THÁI CỦA MỘT VLAN CỤ THỂ.
    Args:
        device_info: Thông tin thiết bị (nếu None, dùng config mặc định)
        vlan_id: ID của VLAN cần kiểm tra
    """
    if vlan_id <= 0:
        return {
            "success": False,
            "error": "VLAN ID không hợp lệ"
        }
    
    if device_info is None:
        device_info = get_default_device_config()
    
    hostname = str(device_info.get("hostname", ""))
    username = str(device_info.get("username", ""))
    password = str(device_info.get("password", ""))
    secret = str(device_info.get("secret")) if device_info.get("secret") else None
    port = int(device_info.get("port", 22))
    
    if not hostname or not username or not password:
        return {
            "success": False,
            "error": "Thiếu thông tin kết nối thiết bị"
        }
    
    ssh_params = get_ssh_params()
    connection_params = {
        'device_type': 'cisco_ios',
        'host': hostname,
        'username': username,
        'password': password,
        'secret': secret,
        'port': port,
        **ssh_params
    }
    
    commands = [
        f"show vlan id {vlan_id}",
        f"show interfaces trunk",
        f"show spanning-tree vlan {vlan_id}"
    ]
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        results = {}
        for cmd in commands:
            output = connection.send_command(cmd, read_timeout=30)
            results[cmd] = output
        
        connection.disconnect()
        
        # Phân tích kết quả
        analysis = parse_vlan_output(results, vlan_id)
        
        return {
            "success": True,
            "vlan_id": vlan_id,
            "outputs": results,
            "analysis": analysis
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def fix_vlan_issue(device_info: Optional[Dict[str, Any]] = None, vlan_id: int = 0, issue_type: str = "") -> Dict[str, Any]:
    """
    TỰ ĐỘNG SỬA LỖI VLAN CƠ BẢN.
    Args:
        device_info: Thông tin thiết bị (nếu None, dùng config mặc định)
        vlan_id: ID của VLAN
        issue_type: Loại lỗi ("missing", "trunk", "stp")
    """
    if vlan_id <= 0:
        return {
            "success": False,
            "error": "VLAN ID không hợp lệ"
        }
    
    if issue_type not in ["missing", "trunk", "stp"]:
        return {
            "success": False,
            "error": f"Loại lỗi không hợp lệ: {issue_type}. Chấp nhận: missing, trunk, stp"
        }
    
    if device_info is None:
        device_info = get_default_device_config()
    
    hostname = str(device_info.get("hostname", ""))
    username = str(device_info.get("username", ""))
    password = str(device_info.get("password", ""))
    secret = str(device_info.get("secret")) if device_info.get("secret") else None
    port = int(device_info.get("port", 22))
    
    if not hostname or not username or not password:
        return {
            "success": False,
            "error": "Thiếu thông tin kết nối thiết bị"
        }
    
    fix_commands = []
    
    if issue_type == "missing":
        fix_commands = [
            f"vlan {vlan_id}",
            f"name AUTO_FIXED_VLAN_{vlan_id}",
            "exit"
        ]
    elif issue_type == "trunk":
        fix_commands = [
            "interface GigabitEthernet0/1",
            f"switchport trunk allowed vlan add {vlan_id}",
            "exit"
        ]
    elif issue_type == "stp":
        fix_commands = [
            f"interface vlan {vlan_id}",
            "spanning-tree vlan priority 4096",
            "exit"
        ]
    
    ssh_params = get_ssh_params()
    connection_params = {
        'device_type': 'cisco_ios',
        'host': hostname,
        'username': username,
        'password': password,
        'secret': secret,
        'port': port,
        **ssh_params
    }
    
    try:
        connection = ConnectHandler(**connection_params)
        
        if secret:
            connection.enable()
        
        connection.config_mode()
        
        for cmd in fix_commands:
            connection.send_command(cmd, expect_string=r'#')
        
        connection.exit_config_mode()
        connection.disconnect()
        
        return {
            "success": True,
            "actions": fix_commands,
            "message": f"Đã áp dụng các cấu hình sửa lỗi cho VLAN {vlan_id}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


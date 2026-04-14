from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from src.tools.network_tools import get_default_device_config, get_ssh_params
from src.tools.parser_tools import parse_cdp_output
from src.tools.parser_tools import *

@tool
def discover_neighbors(device_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    PHÁT HIỆN CÁC THIẾT BỊ LÂN CẬN BẰNG CDP.
    Args:
        device_info: Thông tin thiết bị (nếu None, dùng config mặc định)
    Returns:
        Dict chứa danh sách các thiết bị lân cận
    """
    if device_info is None:
        device_info = get_default_device_config()
    
    hostname = str(device_info.get("hostname", ""))
    username = str(device_info.get("username", ""))
    password = str(device_info.get("password", ""))
    secret = str(device_info.get("secret")) if device_info.get("secret") else None
    port = int(device_info.get("port", 22))
    
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
    
    neighbors = []
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        try:
            cdp_output = connection.send_command("show cdp neighbors detail", read_timeout=30)
            neighbors.extend(parse_cdp_output(cdp_output))
        except:
            pass
        
        connection.disconnect()
        
        return {
            "success": True,
            "device": hostname,
            "neighbors": neighbors,
            "count": len(neighbors)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
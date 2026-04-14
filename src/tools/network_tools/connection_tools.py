from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from src.tools.network_tools import get_default_device_config, get_ssh_params
from src.tools.parser_tools import parse_cdp_output

@tool
def connect_to_device(device_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    KẾT NỐI ĐẾN THIẾT BỊ MẠNG QUA SSH.
    Args:
        device_info: Dict chứa hostname, username, password. (Nếu None, sẽ dùng config mặc định)
    """
    
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
            "error": f"Thiếu thông tin bắt buộc để kết nối: hostname={hostname}, username={username}"
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
    
    try:
        connection = ConnectHandler(**connection_params)
        
        if secret:
            connection.enable()
        
        return {
            "success": True,
            "connection": connection,
            "message": f"Đã kết nối thành công đến {hostname}"
        }
        
    except NetmikoTimeoutException:
        return {
            "success": False,
            "error": f"Timeout khi kết nối đến {hostname}"
        }
    except NetmikoAuthenticationException:
        return {
            "success": False,
            "error": "Sai username hoặc password"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi kết nối: {str(e)}"
        }
    


@tool
def ssh_via_default_device(
    target_host: str,
    target_username: str,
    target_password: str,
    target_command: str = "",
    device_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if device_info is None:
        device_info = get_default_device_config()

    base_conn_result = connect_to_device(device_info)
    if not base_conn_result["success"]:
        return base_conn_result

    connection = base_conn_result["connection"]

    try:
        output = connection.send_command_timing(
            f"ssh -l {target_username} {target_host}"
        )

        if "yes/no" in output.lower():
            output += connection.send_command_timing("yes")

        if "password" in output.lower():
            output += connection.send_command_timing(target_password)

        if target_command:
            output += connection.send_command_timing(target_command)

        connection.disconnect()

        return {
            "success": True,
            "output": output,
            "target_host": target_host
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
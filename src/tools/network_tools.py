import os
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
import yaml

def get_ssh_params():
    """Lấy tham số SSH từ môi trường"""
    return {
        'conn_timeout': int(os.getenv('SSH_TIMEOUT', 60)),
        'auth_timeout': int(os.getenv('SSH_AUTH_TIMEOUT', 30)),
        'global_delay_factor': float(os.getenv('SSH_DELAY_FACTOR', 2)),
    }

def get_default_device_config():
    """Đọc config thiết bị mặc định từ file"""
    try:
        with open("config/devices.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get("default", {})
    except Exception as e:
        print(f"Lỗi đọc config: {e}")
        return {}

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
def execute_show_command(connection: Optional[Any] = None, command: str = "") -> Dict[str, Any]:
    """
    THỰC THI LỆNH SHOW TRÊN THIẾT BỊ.
    Args:
        connection: Đối tượng kết nối Netmiko
        command: Lệnh show cần thực thi
    """
    if connection is None:
        return {
            "success": False,
            "error": "Chưa có kết nối. Hãy gọi connect_to_device trước."
        }
    
    if not command:
        return {
            "success": False,
            "error": "Chưa nhập lệnh cần thực thi."
        }
    
    try:
        output = connection.send_command(command, read_timeout=30)
        return {
            "success": True,
            "command": command,
            "output": output
        }
    except Exception as e:
        return {
            "success": False,
            "command": command,
            "error": str(e)
        }


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

@tool
def configure_static_route(device_info: Optional[Dict[str, Any]] = None, 
                           destination_network: str = "", 
                           next_hop: str = "") -> Dict[str, Any]:
    """
    CẤU HÌNH STATIC ROUTE TRÊN ROUTER.
    Args:
        device_info: Thông tin thiết bị
        destination_network: Mạng đích (ví dụ: 192.168.10.0 255.255.255.0)
        next_hop: Next-hop IP hoặc exit interface
    """
    if not destination_network or not next_hop:
        return {
            "success": False,
            "error": "Thiếu thông tin: destination_network và next_hop là bắt buộc"
        }
    
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
    
    config_commands = [
        f"ip route {destination_network} {next_hop}"
    ]
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        connection.config_mode()
        output = connection.send_config_set(config_commands)
        connection.exit_config_mode()
        connection.disconnect()
        
        return {
            "success": True,
            "commands": config_commands,
            "message": f"Đã cấu hình static route: {destination_network} -> {next_hop}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def configure_ospf(device_info: Optional[Dict[str, Any]] = None,
                   process_id: int = 1,
                   network: str = "",
                   wildcard_mask: str = "",
                   area: int = 0) -> Dict[str, Any]:
    """
    CẤU HÌNH OSPF TRÊN ROUTER.
    Args:
        device_info: Thông tin thiết bị
        process_id: OSPF process ID (mặc định: 1)
        network: Mạng cần quảng bá (ví dụ: 192.168.10.0)
        wildcard_mask: Wildcard mask (ví dụ: 0.0.0.255)
        area: OSPF area (mặc định: 0)
    """
    if not network or not wildcard_mask:
        return {
            "success": False,
            "error": "Thiếu thông tin: network và wildcard_mask là bắt buộc"
        }
    
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
    
    config_commands = [
        f"router ospf {process_id}",
        f"network {network} {wildcard_mask} area {area}",
        "exit"
    ]
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        connection.config_mode()
        output = connection.send_config_set(config_commands)
        connection.exit_config_mode()
        connection.disconnect()
        
        return {
            "success": True,
            "commands": config_commands,
            "message": f"Đã cấu hình OSPF process {process_id} cho mạng {network}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def ping_test(device_info: Optional[Dict[str, Any]] = None,
              target_ip: str = "",
              count: int = 5) -> Dict[str, Any]:
    """
    KIỂM TRA KẾT NỐI PING ĐẾN ĐỊA CHỈ IP.
    Args:
        device_info: Thông tin thiết bị
        target_ip: Địa chỉ IP cần ping
        count: Số lần ping (mặc định: 5)
    """
    if not target_ip:
        return {
            "success": False,
            "error": "Thiếu target_ip"
        }
    
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
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        ping_output = connection.send_command(f"ping {target_ip} repeat {count}", read_timeout=60)
        connection.disconnect()
        
        # Phân tích kết quả ping
        success_rate = 0
        if "Success rate is" in ping_output:
            import re
            match = re.search(r"Success rate is (\d+) percent", ping_output)
            if match:
                success_rate = int(match.group(1))
        
        return {
            "success": True,
            "target": target_ip,
            "success_rate": success_rate,
            "output": ping_output,
            "reachable": success_rate > 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def get_routing_table(device_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    LẤY BẢNG ĐỊNH TUYẾN CỦA ROUTER.
    
    Args:
        device_info: Thông tin thiết bị
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
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        routing_table = connection.send_command("show ip route", read_timeout=30)
        connection.disconnect()
        
        return {
            "success": True,
            "routing_table": routing_table
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def get_interface_ip(device_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    LẤY ĐỊA CHỈ IP TRÊN TẤT CẢ CÁC INTERFACE.
    Args:
        device_info: Thông tin thiết bị
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
    
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()
        
        ip_brief = connection.send_command("show ip interface brief", read_timeout=30)
        connection.disconnect()
        
        # Parse kết quả
        interfaces = []
        lines = ip_brief.strip().split('\n')
        for line in lines[1:]:  # Bỏ header
            parts = line.split()
            if len(parts) >= 2:
                interfaces.append({
                    "interface": parts[0],
                    "ip_address": parts[1] if parts[1] != "unassigned" else None,
                    "status": parts[4] if len(parts) > 4 else "unknown"
                })
        
        return {
            "success": True,
            "interfaces": interfaces,
            "raw_output": ip_brief
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def parse_cdp_output(output: str) -> list:
    """Parse output của lệnh show cdp neighbors detail"""
    neighbors = []
    lines = output.split('\n')
    current = {}
    
    for line in lines:
        if 'Device ID:' in line:
            if current:
                neighbors.append(current)
            current = {}
            current['device_id'] = line.split('Device ID:')[1].strip()
        elif 'IP address:' in line:
            current['ip_address'] = line.split('IP address:')[1].strip()
        elif 'Platform:' in line:
            current['platform'] = line.split('Platform:')[1].strip()
        elif 'Interface:' in line:
            current['local_interface'] = line.split('Interface:')[1].strip()
        elif 'Port ID (outgoing port):' in line:
            current['remote_interface'] = line.split('Port ID (outgoing port):')[1].strip()
    
    if current:
        neighbors.append(current)
    
    return neighbors

def parse_lldp_output(output: str) -> list:
    """Parse output của lệnh show lldp neighbors detail"""
    neighbors = []
    lines = output.split('\n')
    current = {}
    
    for line in lines:
        if 'System Name:' in line:
            if current:
                neighbors.append(current)
            current = {}
            current['device_id'] = line.split('System Name:')[1].strip()
        elif 'Management Addresses:' in line:
            current['ip_address'] = line.split('Management Addresses:')[1].strip()
        elif 'Local Intf:' in line:
            current['local_interface'] = line.split('Local Intf:')[1].strip()
        elif 'Port id:' in line:
            current['remote_interface'] = line.split('Port id:')[1].strip()
    
    if current:
        neighbors.append(current)
    
    return neighbors

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

def parse_vlan_output(outputs: dict, vlan_id: int) -> dict:
    """Phân tích output VLAN"""
    import re
    
    analysis = {
        "vlan_exists": False,
        "vlan_name": None,
        "interfaces": [],
        "issues": []
    }
    
    vlan_output = outputs.get(f"show vlan id {vlan_id}", "")
    
    # Kiểm tra VLAN tồn tại
    if f"VLAN {vlan_id}" in vlan_output or f"VLAN0{vlan_id}" in vlan_output:
        analysis["vlan_exists"] = True
        
        # Tìm tên VLAN
        match = re.search(rf"VLAN{vlan_id}\s+(\S+)", vlan_output)
        if match:
            analysis["vlan_name"] = match.group(1)
        
        # Tìm interfaces trong VLAN
        interfaces = re.findall(r'(Gi|Fa|Et)\S+', vlan_output)
        analysis["interfaces"] = interfaces
        
        if not interfaces:
            analysis["issues"].append({
                "type": "no_ports",
                "severity": "high",
                "description": f"VLAN {vlan_id} không có port nào được gán"
            })
    
    else:
        analysis["issues"].append({
            "type": "missing_vlan",
            "severity": "critical",
            "description": f"VLAN {vlan_id} không tồn tại"
        })
    
    # Kiểm tra trunk
    trunk_output = outputs.get("show interfaces trunk", "")
    if f"VLAN{vlan_id}" not in trunk_output and analysis["vlan_exists"]:
        analysis["issues"].append({
            "type": "trunk_issue",
            "severity": "medium",
            "description": f"VLAN {vlan_id} không được phép trên trunk"
        })
    
    return analysis
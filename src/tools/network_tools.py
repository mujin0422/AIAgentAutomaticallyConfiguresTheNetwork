import cmd
import ipaddress
import os
import re
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
import yaml
from src.tools.parser_tools import *

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
        
    try:
        connection = ConnectHandler(**connection_params)
        if secret:
            connection.enable()

        output = connection.send_command("show cdp neighbors detail", read_timeout=30)
        neighbors = parse_cdp_output(output)
        
        connection.disconnect()
        
        return {
            "success": True,
            "device": hostname,
            "neighbors": neighbors,
            "raw_output": output,
            "count": len(neighbors)
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

        output = connection.send_command("show ip interface brief", read_timeout=30)
        interfaces = parse_interface_ip(output)

        connection.disconnect()
               
        return {
            "success": True,
            "interfaces": interfaces,
            "raw_output": output
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }    



@tool
def ping_test(device_info: Optional[Dict[str, Any]] = None, target_ip: str = "") -> Dict[str, Any]:
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
        
        ping_output = connection.send_command(f"ping {target_ip}", read_timeout=60)
        connection.disconnect()
        
        # Phân tích kết quả ping
        success_rate = 0
        if "Success rate is" in ping_output:
            match = re.search(r"Success rate is (\d+) percent", ping_output)
            if match:
                success_rate = int(match.group(1))
        
        return {
            "success": True,
            "target": target_ip,
            "success_rate": success_rate,
            "output": ping_output,
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
def ssh_to_neighbor(device_info: Optional[Dict[str, Any]] = None, 
                   neighbor_ip: str = "",
                   neighbor_username: str = "",
                   neighbor_password: str = "",
                   neighbor_secret: str = None) -> Dict[str, Any]:
    """
    SSH TỪ THIẾT BỊ HIỆN TẠI ĐẾN THIẾT BỊ LÂN CẬN (SSH HOPPING).
    
    Args:
        device_info: Thông tin thiết bị nguồn (đang đứng)
        neighbor_ip: IP của thiết bị lân cận cần SSH đến
        neighbor_username: Username của thiết bị lân cận
        neighbor_password: Password của thiết bị lân cận
        neighbor_secret: Enable secret của thiết bị lân cận (nếu có)
    
    Returns:
        Dict chứa kết quả kết nối và thông tin thiết bị đích
    """
    if not neighbor_ip or not neighbor_username or not neighbor_password:
        return {
            "success": False,
            "error": "Thiếu thông tin kết nối đến thiết bị lân cận (neighbor_ip, username, password)"
        }
    
    if device_info is None:
        device_info = get_default_device_config()
    
    # Kết nối đến thiết bị nguồn
    source_hostname = str(device_info.get("hostname", ""))
    source_username = str(device_info.get("username", ""))
    source_password = str(device_info.get("password", ""))
    source_secret = str(device_info.get("secret")) if device_info.get("secret") else None
    source_port = int(device_info.get("port", 22))
    
    ssh_params = get_ssh_params()
    source_connection_params = {
        'device_type': 'cisco_ios',
        'host': source_hostname,
        'username': source_username,
        'password': source_password,
        'secret': source_secret,
        'port': source_port,
        **ssh_params
    }
    
    try:
        # Kết nối đến thiết bị nguồn
        source_connection = ConnectHandler(**source_connection_params)
        if source_secret:
            source_connection.enable()
        
        # Từ thiết bị nguồn, SSH sang thiết bị lân cận
        ssh_command = f"ssh -l {neighbor_username} {neighbor_ip}"
        ssh_output = source_connection.send_command(
            ssh_command, 
            expect_string=r"password:",
            read_timeout=30
        )
        
        # Gửi password
        ssh_output += source_connection.send_command(
            neighbor_password,
            expect_string=r"#|>",
            read_timeout=30
        )
        
        # Kiểm tra xem đã vào được enable mode chưa
        if neighbor_secret:
            ssh_output += source_connection.send_command(
                "enable",
                expect_string=r"Password:",
                read_timeout=10
            )
            ssh_output += source_connection.send_command(
                neighbor_secret,
                expect_string=r"#",
                read_timeout=10
            )
        
        # Lấy hostname của thiết bị đích để xác nhận
        hostname_check = source_connection.send_command("show version | include uptime", read_timeout=10)
        
        source_connection.disconnect()
        
        return {
            "success": True,
            "source_device": source_hostname,
            "target_device": neighbor_ip,
            "target_hostname": hostname_check.split()[0] if hostname_check else neighbor_ip,
            "message": f"✅ Đã SSH thành công từ {source_hostname} đến {neighbor_ip}",
            "output": ssh_output
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi SSH hopping: {str(e)}",
            "source_device": source_hostname if 'source_hostname' in locals() else "unknown",
            "target_device": neighbor_ip
        }


@tool
def explore_network_hierarchy(start_device_info: Optional[Dict[str, Any]] = None,
                              max_hops: int = 3,
                              discovered_devices: Optional[list] = None) -> Dict[str, Any]:
    """
    KHÁM PHÁ TOÀN BỘ MẠNG BẰNG CÁCH ĐỆ QUY SSH QUA CÁC THIẾT BỊ LÂN CẬN.
    
    Args:
        start_device_info: Thông tin thiết bị bắt đầu
        max_hops: Số hop tối đa (tránh vòng lặp vô hạn)
        discovered_devices: Danh sách các thiết bị đã phát hiện (dùng cho đệ quy)
    
    Returns:
        Dict chứa cấu trúc phân cấp của toàn bộ mạng
    """
    if discovered_devices is None:
        discovered_devices = []
    
    if start_device_info is None:
        start_device_info = get_default_device_config()
    
    current_hostname = start_device_info.get("hostname", "unknown")
    
    # Tránh lặp vô hạn
    if current_hostname in discovered_devices:
        return {
            "success": False,
            "error": f"Phát hiện vòng lặp tại {current_hostname}",
            "device": current_hostname,
            "hop": len(discovered_devices)
        }
    
    discovered_devices.append(current_hostname)
    
    if len(discovered_devices) > max_hops:
        return {
            "success": False,
            "error": f"Đã đạt đến giới hạn {max_hops} hops",
            "devices_discovered": discovered_devices
        }
    
    try:
        # Tìm các thiết bị lân cận của thiết bị hiện tại
        neighbors_result = discover_neighbors(start_device_info)
        
        if not neighbors_result.get("success"):
            return {
                "success": False,
                "error": f"Không thể phát hiện neighbors từ {current_hostname}",
                "device": current_hostname
            }
        
        neighbors = neighbors_result.get("neighbors", [])
        
        network_tree = {
            "current_device": current_hostname,
            "neighbors": [],
            "hop": len(discovered_devices) - 1
        }
        
        # Đệ quy khám phá từng neighbor
        for neighbor in neighbors:
            neighbor_ip = neighbor.get("neighbor_ip")
            neighbor_hostname = neighbor.get("neighbor_hostname", neighbor_ip)
            
            # Tạo device info cho neighbor
            neighbor_device_info = {
                "hostname": neighbor_ip,  # Dùng IP để kết nối
                "username": start_device_info.get("username", ""),
                "password": start_device_info.get("password", ""),
                "secret": start_device_info.get("secret"),
                "port": start_device_info.get("port", 22),
                "device_type": "cisco_ios"
            }
            
            # Kiểm tra xem đã khám phá chưa
            if neighbor_hostname not in discovered_devices:
                sub_result = explore_network_hierarchy(
                    neighbor_device_info,
                    max_hops,
                    discovered_devices.copy()
                )
                
                network_tree["neighbors"].append({
                    "neighbor_name": neighbor_hostname,
                    "neighbor_ip": neighbor_ip,
                    "connection_info": neighbor.get("connection_info", {}),
                    "subtree": sub_result if sub_result.get("success") else None
                })
        
        return {
            "success": True,
            "network_topology": network_tree,
            "devices_discovered": discovered_devices,
            "total_devices": len(discovered_devices)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "device": current_hostname,
            "devices_discovered": discovered_devices
        }


@tool
def execute_on_multiple_devices(devices: list, command: str) -> Dict[str, Any]:
    """
    THỰC THI LỆNH TRÊN NHIỀU THIẾT BỊ THÔNG QUA SSH HOPPING.
    
    Args:
        devices: Danh sách các thiết bị theo thứ tự cần SSH qua
                Ví dụ: [
                    {"hostname": "192.168.1.1", "username": "admin", "password": "pass1"},
                    {"hostname": "10.0.0.2", "username": "admin", "password": "pass2"},
                    {"hostname": "10.0.0.3", "username": "admin", "password": "pass3"}
                ]
        command: Lệnh cần thực thi trên thiết bị cuối cùng
    
    Returns:
        Dict chứa kết quả sau khi SSH qua các hop
    """
    if not devices or len(devices) == 0:
        return {
            "success": False,
            "error": "Danh sách thiết bị trống"
        }
    
    if not command:
        return {
            "success": False,
            "error": "Chưa nhập lệnh cần thực thi"
        }
    
    current_connection = None
    hop_results = []
    
    try:
        # Kết nối lần lượt qua các hop
        for idx, device in enumerate(devices):
            hostname = device.get("hostname")
            username = device.get("username")
            password = device.get("password")
            secret = device.get("secret")
            port = device.get("port", 22)
            
            if idx == 0:
                # Hop đầu tiên: kết nối trực tiếp
                connection_params = {
                    'device_type': 'cisco_ios',
                    'host': hostname,
                    'username': username,
                    'password': password,
                    'secret': secret,
                    'port': port,
                    **get_ssh_params()
                }
                current_connection = ConnectHandler(**connection_params)
                if secret:
                    current_connection.enable()
                
                hop_results.append({
                    "hop": idx + 1,
                    "device": hostname,
                    "status": "connected"
                })
                
            else:
                # Các hop tiếp theo: SSH từ hop trước
                ssh_command = f"ssh -l {username} {hostname}"
                current_connection.send_command(
                    ssh_command,
                    expect_string=r"password:",
                    read_timeout=30
                )
                current_connection.send_command(
                    password,
                    expect_string=r"#|>",
                    read_timeout=30
                )
                
                if secret:
                    current_connection.send_command("enable", expect_string=r"Password:", read_timeout=10)
                    current_connection.send_command(secret, expect_string=r"#", read_timeout=10)
                
                hop_results.append({
                    "hop": idx + 1,
                    "device": hostname,
                    "status": "ssh_hop_successful"
                })
        
        # Thực thi lệnh trên thiết bị cuối cùng
        output = current_connection.send_command(command, read_timeout=30)
        
        # Đóng kết nối
        if current_connection:
            current_connection.disconnect()
        
        return {
            "success": True,
            "hops": hop_results,
            "final_device": devices[-1].get("hostname"),
            "command": command,
            "output": output,
            "total_hops": len(devices)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "hops_completed": hop_results,
            "failed_at_hop": len(hop_results) + 1
        }
    
@tool
def configure_static_route(
    connection: Optional[Any] = None,
    network: str = "",
    mask: str = "255.255.255.0",
    next_hop: str = ""
) -> Dict[str, Any]:
    """
    CẤU HÌNH STATIC ROUTE.
    VD: network='10.0.0.0', mask='255.255.255.0', next_hop='192.168.1.1'
    """
    if connection is None:
        return {
            "success": False,
            "error": "Không có kết nối đến thiết bị"
        }
    
    try:
        # Validate IP addresses
        ipaddress.IPv4Network(f"{network}/{mask}")
        ipaddress.IPv4Address(next_hop)
        
        command = f"ip route {network} {mask} {next_hop}"
        output = connection.send_config_set([command])
        
        return {
            "success": True,
            "output": output,
            "message": f"Đã cấu hình static route: {command}"
        }
        
    except ValueError as ve:
        return {
            "success": False,
            "error": f"Địa chỉ IP không hợp lệ: {ve}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi khi cấu hình static route: {e}"
        }

@tool
def set_hostname(connection: Optional[Any] = None, new_hostname: str = "") -> Dict[str, Any]:
    """
    ĐẶT TÊN ROUTER (HOSTNAME).
    """
    if connection is None:
        return {"success": False, "error": "Chưa connect"}
    
    if not new_hostname:
        return {"success": False, "error": "Thiếu new_hostname"}
    
    cmds = ["configure terminal", f"hostname {new_hostname}", "end", "wr"]
    try:
        output = ""
        for cmd in cmds:
            output += connection.send_command(cmd)
        return {
            "success": True,
            "new_hostname": new_hostname,
            "output": output
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def configure_ospf(
    connection: Optional[Any] = None, 
    process_id: int = 1, 
    network: str = "", 
    wildcard: str = "0.0.0.255", 
    area: int = 0
)-> Dict[str, Any]:
    """ CẤU HÌNH OSPF. VD: process=1, network='192.168.1.0', wildcard='0.0.0.255', area=0 """
    if connection is None:
        return {"success": False, "error": "Chua connect"}
    cmds = [ "router ospf {}".format(process_id), " network {} {} area {}".format(network, wildcard, area), "end" ]
    try:
        output = ""
        for cmd in cmds:
            output += connection.send_command(cmd)
        return {
            "success": True, 
            "process_id": process_id, 
            "commands": cmds, 
            "output": output 
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
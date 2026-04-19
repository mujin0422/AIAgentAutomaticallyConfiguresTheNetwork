import cmd
import ipaddress
from multiprocessing.dummy import connection
from multiprocessing import connection
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
        output = connection.send_command("show ip interface brief")
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
        match = re.search(r"Success rate is (\d+)\s*percent", ping_output)
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
            expect_string=r"[Pp]assword:",
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
    hostname: str,
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
        ipaddress.IPv4Network(f"{network}/{mask}")
        ipaddress.IPv4Address(next_hop)

        command = f"ip route {network} {mask} {next_hop}"
        output = connection.send_config_set([command])

        connection.disconnect()

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
    
    try:
        output = connection.send_config_set([
            f"hostname {new_hostname}"
        ])
        connection.save_config()
        
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
    cmds = [
        f"router ospf {process_id}",
        f"network {network} {wildcard} area {area}"
    ]
    try:
        output = connection.send_config_set(cmds)

        return {
            "success": True, 
            "process_id": process_id, 
            "commands": cmds, 
            "output": output 
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    
def get_default_device_config():
# 1. Ưu tiên ENV
    if os.getenv("DEFAULT_HOST"):
        return {
            "hostname": os.getenv("DEFAULT_HOST"),
            "username": os.getenv("DEFAULT_USER"),
            "password": os.getenv("DEFAULT_PASS"),
            "secret": os.getenv("DEFAULT_SECRET"),
            "port": int(os.getenv("DEFAULT_PORT", 22)),
            "device_type": os.getenv("DEVICE_TYPE", "cisco_ios")
        }

    # 2. Nếu không có → đọc YAML
    try:
        with open("config/devices.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        default_name = config.get("default_device")
        device = config.get(default_name)

        if not device:
            raise ValueError("Không tìm thấy default_device trong YAML")

        return device

    except Exception:
        return None
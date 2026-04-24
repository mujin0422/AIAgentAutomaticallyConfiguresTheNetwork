from datetime import datetime
import os
import re
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from netmiko import ConnectHandler
import yaml
from src.tools.parser_tools import *
from src.tools.config_backup import ConfigBackupManager

# Khởi tạo backup manager toàn cục
backup_manager = ConfigBackupManager()

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

@tool
def configure_interface_ip(hostname: str, 
                           interface: str, 
                           ip_address: str, 
                           subnet_mask: str,
                           description: str = "") -> Dict[str, Any]:
    """CẤU HÌNH IP CHO INTERFACE (có backup đa phiên bản)"""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]

        config_commands = [
            f"interface {interface}",
            f"ip address {ip_address} {subnet_mask}",
            "no shutdown",
            "exit"
        ]

        # Lưu backup với nhiều phiên bản
        backup_config = connection.send_command_timing(f"show running-config interface {interface}")
        backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="interface",
            content=backup_config,
            description=description or f"Config interface {interface} with {ip_address}/{subnet_mask}"
        )

        output = connection.send_config_set(config_commands)
        verify = connection.send_command_timing(f"show running-config interface {interface} | include ip address") 

        connection.disconnect()

        return {
            "success": True,
            "device": hostname,
            "interface": interface,
            "ip_address": ip_address,
            "subnet_mask": subnet_mask,
            "config_output": output,
            "verification": verify,
            "backup_id": backup_id,  # ID để rollback sau
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def configure_ospf(hostname: str,
                   process_id: int,
                   network: str,
                   wildcard_mask: str,
                   area: int,
                   description: str = "") -> Dict[str,Any]:
    """CẤU HÌNH OSPF (có backup đa phiên bản)"""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]

        backup_ospf = connection.send_command_timing(f"show run | section router ospf")
        backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="ospf",
            content=backup_ospf,
            description=description or f"OSPF config (process {process_id})"
        )

        config_commands = [
            f"router ospf {process_id}",
            f"network {network} {wildcard_mask} area {area}",
            "exit"
        ]

        output = connection.send_config_set(config_commands)
        verify = connection.send_command_timing(f"show ip ospf interface brief")

        connection.disconnect()

        return {
            "success": True,
            "device": hostname,
            "process_id": process_id,
            "network": network,
            "area": area,
            "config_output": output,
            "verification": verify,
            "backup_id": backup_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def configure_static_route(hostname: str,
                           destination_network: str,
                           subnet_mask: str,
                           next_hop: str,
                           description: str = "") -> Dict[str, Any]:
    """CẤU HÌNH ROUTE TĨNH (có backup đa phiên bản)"""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]

        backup_routes = connection.send_command_timing("show ip route static")
        backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="static_route",
            content=backup_routes,
            description=description or f"Static route to {destination_network}/{subnet_mask}"
        )

        # Kiểm tra next_hop là IP hay interface
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', next_hop):
            route_command = f"ip route {destination_network} {subnet_mask} {next_hop}"
        else:
            route_command = f"ip route {destination_network} {subnet_mask} {next_hop}"
        
        output = connection.send_config_set([route_command])
        verify = connection.send_command_timing(f"show ip route {destination_network}")
        
        connection.disconnect()

        return {
            "success": True,
            "device": hostname,
            "destination": destination_network,
            "next_hop": next_hop,
            "config_output": output,
            "verification": verify,
            "backup_id": backup_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def configure_vlan(hostname: str, 
                   vlan_id: int, 
                   vlan_name: str, 
                   ports: List[str] = None,
                   description: str = "") -> Dict[str, Any]:
    """CẤU HÌNH VLAN (có backup đa phiên bản)"""
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]
        
        # Backup VLAN config hiện tại
        backup_vlan = connection.send_command_timing(f"show vlan id {vlan_id}" if vlan_id else "show vlan brief")
        backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="vlan",
            content=backup_vlan,
            description=description or f"VLAN {vlan_id}: {vlan_name}"
        )
        
        config_commands = [
            f"vlan {vlan_id}",
            f"name {vlan_name}",
            "exit"
        ]
        
        # Gán ports vào VLAN nếu có
        if ports:
            for port in ports:
                config_commands.extend([
                    f"interface {port}",
                    f"switchport mode access",
                    f"switchport access vlan {vlan_id}",
                    "no shutdown",
                    "exit"
                ])
        
        output = connection.send_config_set(config_commands)
        verify = connection.send_command_timing(f"show vlan id {vlan_id}")
        
        connection.disconnect()
        
        return {
            "success": True,
            "device": hostname,
            "vlan_id": vlan_id,
            "vlan_name": vlan_name,
            "ports": ports,
            "config_output": output,
            "verification": verify,
            "backup_id": backup_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    
@tool
def configure_hostname(hostname: str, new_hostname: str, description: str = "") -> Dict[str, Any]:
    """
    ĐỔI TÊN (HOSTNAME) CHO THIẾT BỊ MẠNG.
    
    Args:
        hostname: Tên hiện tại của thiết bị (VD: "P1")
        new_hostname: Tên mới muốn đặt (VD: "CORE_ROUTER_1")
        description: Mô tả cho thay đổi này (tùy chọn)
    
    Returns:
        Dict chứa kết quả cấu hình
    """
    try:
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]
        
        # Lưu backup hostname hiện tại
        backup_hostname = connection.send_command_timing("show running-config | include hostname")
        backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="hostname",
            content=backup_hostname,
            description=description or f"Change hostname from {hostname} to {new_hostname}"
        )
        
        # Lệnh đổi hostname
        config_commands = [f"hostname {new_hostname}"]
        output = connection.send_config_set(config_commands)
        
        # Verify - kiểm tra hostname đã đổi chưa
        verify = connection.send_command_timing("show running-config | include hostname")
        
        connection.disconnect()
        
        return {
            "success": True,
            "device": hostname,
            "old_hostname": hostname,
            "new_hostname": new_hostname,
            "config_output": output,
            "verification": verify,
            "backup_id": backup_id,
            "message": f"Đã đổi tên thiết bị từ '{hostname}' thành '{new_hostname}'",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    
@tool
def smart_rollback(hostname: str, 
                   config_type: str = None, 
                   version: int = 1,
                   backup_id: str = None) -> Dict[str, Any]:
    """
    ROLLBACK THÔNG MINH - Hỗ trợ tất cả các loại cấu hình
    
    Args:
        hostname: Tên thiết bị
        config_type: Loại config (interface, ospf, static_route, vlan, bgp, port_security, acl, ntp)
                      Nếu None thì rollback toàn bộ config
        version: Số thứ tự (1: mới nhất, 2: cũ hơn,...)
        backup_id: Hoặc dùng ID cụ thể
    
    Returns:
        Kết quả rollback
    """
    try:
        # Lấy danh sách backups
        if config_type:
            backups = backup_manager.get_backups(hostname, config_type)
        else:
            backups = backup_manager.get_backups(hostname)
        
        if not backups:
            return {
                "success": False,
                "error": f"Không tìm thấy backup nào cho {hostname}" + 
                        (f" với loại {config_type}" if config_type else "")
            }
        
        # Chọn backup
        target_backup = None
        if backup_id:
            for b in backups:
                if b["backup_id"] == backup_id:
                    target_backup = b
                    break
        elif version:
            if 1 <= version <= len(backups):
                target_backup = backups[version - 1]
            else:
                return {
                    "success": False,
                    "error": f"Version {version} không tồn tại. Có {len(backups)} bản backup"
                }
        
        if not target_backup:
            return {"success": False, "error": "Không xác định được bản backup"}
        
        # Đọc nội dung backup
        backup_content = backup_manager.get_backup_content(target_backup["backup_id"])
        if not backup_content:
            return {"success": False, "error": "Không thể đọc file backup"}
        
        # Kết nối và rollback
        conn_res = connect_to_device(hostname)
        if not conn_res["success"]:
            return conn_res
        
        connection = conn_res["connection"]
        
        # Backup hiện tại trước khi rollback
        current_config = connection.send_command_timing("show running-config")
        current_backup_id = backup_manager.create_backup(
            hostname=hostname,
            config_type="pre_rollback",
            content=current_config,
            description=f"Auto backup before rollback to {target_backup['backup_id']}"
        )
        
        # Thực hiện rollback
        output = connection.send_config_set(backup_content.split('\n'))
        
        connection.disconnect()
        
        return {
            "success": True,
            "device": hostname,
            "rolled_back_to": {
                "backup_id": target_backup["backup_id"],
                "config_type": target_backup["config_type"],
                "timestamp": target_backup["timestamp"],
                "description": target_backup["description"]
            },
            "current_backup_id": current_backup_id,
            "output": output,
            "message": f"✅ Đã rollback {hostname} về bản backup {target_backup['config_type']} từ {target_backup['timestamp']}"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
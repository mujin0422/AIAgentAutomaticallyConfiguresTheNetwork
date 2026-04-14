import re
from typing import Dict, List, Any
from langchain_core.tools import tool

def parse_cdp_output(output: str) -> Dict[str, Any]:
    """
    Phân tích output của lệnh 'show cdp neighbors detail' để trích xuất thông tin thiết bị lân cận.
    Args:
        output: Output từ lệnh 'show cdp neighbors detail'
    Returns:
        Dict chứa danh sách các thiết bị lân cận và tổng hợp thông tin
    """
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

def parse_interface_ip(output: str) -> List[Dict[str, Any]]:
    """
    Phân tích output của lệnh 'show ip interface brief' để trích xuất thông tin IP trên các interface.
    Args:
        output: Output từ lệnh 'show ip interface brief'
    Returns:
        List các interface với IP address và trạng thái
    """
    interfaces = []
    lines = output.strip().split('\n')
    
    for line in lines[1:]:  # Bỏ header
        parts = line.split()
        if len(parts) >= 2:
            interfaces.append({
                "interface": parts[0],
                "ip_address": parts[1] if parts[1] != "unassigned" else None,
                "status": parts[4] if len(parts) > 4 else "unknown"
            })
    
    return interfaces

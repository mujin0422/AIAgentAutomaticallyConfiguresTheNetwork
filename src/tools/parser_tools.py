import re
from typing import Dict, List, Any
from langchain_core.tools import tool

@tool
def detect_config_issues(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phát hiện các vấn đề cấu hình tổng quát từ dữ liệu network.
    """
    issues = []

    # Check VLAN
    if "vlan" in data:
        vlan_analysis = parse_vlan_output(data["vlan"])
        if vlan_analysis["issue_count"] > 0:
            issues.extend(vlan_analysis["issues"])

    # Check interface
    if "interface" in data:
        interface_analysis = analyze_interface_errors(data["interface"])
        if interface_analysis["summary"]["has_issues"]:
            issues.append({
                "type": "interface_issue",
                "severity": interface_analysis["summary"]["severity"],
                "description": "Interface có lỗi"
            })

    return {
        "total_issues": len(issues),
        "issues": issues
    }

@tool
def parse_vlan_output(vlan_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phân tích output VLAN để tìm vấn đề.
    Args:
        vlan_data: Dict chứa output của các lệnh show VLAN 
    Returns:
        Dict chứa phân tích chi tiết
    """
    analysis = {
        "vlan_status": "unknown",
        "issues": [],
        "details": {}
    }
    
    results = vlan_data.get("results", {})
    vlan_id = vlan_data.get("vlan_id")
    
    # Phân tích show vlan
    vlan_output = results.get(f"show vlan id {vlan_id}", "")
    if "VLAN" not in vlan_output:
        analysis["issues"].append({
            "type": "missing_vlan",
            "severity": "critical",
            "description": f"VLAN {vlan_id} không tồn tại trong cơ sở dữ liệu VLAN"
        })
    elif "active" not in vlan_output.lower():
        analysis["issues"].append({
            "type": "vlan_inactive",
            "severity": "high",
            "description": f"VLAN {vlan_id} không ở trạng thái active"
        })
    
    # Phân tích trunk
    trunk_output = results.get("show interfaces trunk", "")
    if vlan_id and f"VLAN{vlan_id}" not in trunk_output:
        analysis["issues"].append({
            "type": "trunk_issue",
            "severity": "high",
            "description": f"VLAN {vlan_id} không được phép trên trunk"
        })
    
    # Đếm số lượng vấn đề
    analysis["issue_count"] = len(analysis["issues"])
    analysis["vlan_status"] = "critical" if analysis["issue_count"] > 0 else "healthy"
    
    return analysis

@tool
def analyze_interface_errors(interface_output: str) -> Dict[str, Any]:
    """
    Phân tích lỗi interface từ output show interfaces.
    Args:
        interface_output: Output của lệnh show interfaces
    Returns:
        Dict chứa phân tích lỗi
    """
    errors = {
        "input_errors": [],
        "output_errors": [],
        "crc_errors": [],
        "duplex_mismatch": False,
        "summary": {}
    }
    
    # Tìm lỗi CRC
    crc_match = re.search(r'(\d+)\s+input errors with CRC', interface_output)
    if crc_match and int(crc_match.group(1)) > 0:
        errors["crc_errors"].append({
            "count": crc_match.group(1),
            "suggestion": "Kiểm tra cáp mạng hoặc duplex mismatch"
        })
    
    # Kiểm tra duplex
    if "half-duplex" in interface_output.lower():
        errors["duplex_mismatch"] = True
        errors["suggestions"] = "Cấu hình duplex tự động hoặc force full-duplex"
    
    # Tổng hợp
    total_errors = len(errors["input_errors"]) + len(errors["output_errors"]) + len(errors["crc_errors"])
    errors["summary"] = {
        "total_errors": total_errors,
        "has_issues": total_errors > 0 or errors["duplex_mismatch"],
        "severity": "high" if errors["crc_errors"] else "medium"
    }
    
    return errors
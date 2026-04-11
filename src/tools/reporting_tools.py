from typing import Dict, Any
from langchain_core.tools import tool
from datetime import datetime

@tool
def generate_report(analysis_data: Dict[str, Any]) -> str:
    """
    Tạo báo cáo chi tiết về sự cố và giải pháp.
    Args:
        analysis_data: Dict chứa kết quả phân tích 
    Returns:
        String chứa báo cáo hoàn chỉnh
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
╔════════════════════════════════════════════════════════════════╗
║              BÁO CÁO PHÂN TÍCH SỰ CỐ MẠNG                      ║
╚════════════════════════════════════════════════════════════════╝
- Thời gian: {timestamp}
- Thiết bị: {analysis_data.get('target_device', 'N/A')}
- VLAN: {analysis_data.get('vlan_id', 'N/A')}
─────────────────────────────────────────────────────────────────
===> VẤN ĐỀ PHÁT HIỆN
─────────────────────────────────────────────────────────────────
"""
    
    # Thêm các vấn đề phát hiện được
    issues = analysis_data.get('issues', [])
    if issues:
        for i, issue in enumerate(issues, 1):
            report += f"{i}. {issue.get('description', 'N/A')}\n"
            report += f"   Mức độ: {issue.get('severity', 'medium').upper()}\n"
            if issue.get('details'):
                report += f"   Chi tiết: {issue['details']}\n"
            report += "\n"
    else:
        report += "Không phát hiện vấn đề bất thường.\n\n"
    
    report += "─────────────────────────────────────────────────────────────────\n\n"
    
    # Thêm nguyên nhân gốc rễ
    report += "NGUYÊN NHÂN GỐC RỄ:\n"
    report += "─────────────────────────────────────────────────────────────────\n"
    root_cause = analysis_data.get('root_cause', 'Chưa xác định được nguyên nhân cụ thể.')
    report += f"{root_cause}\n\n"
    
    # Thêm đề xuất giải pháp
    report += "ĐỀ XUẤT GIẢI PHÁP:\n"
    report += "─────────────────────────────────────────────────────────────────\n"
    recommendations = analysis_data.get('recommendations', [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
    else:
        report += "Không có đề xuất cụ thể.\n"
    
    # Thêm hành động đã thực hiện
    if analysis_data.get('actions_taken'):
        report += "\nHÀNH ĐỘNG ĐÃ THỰC HIỆN:\n"
        report += "─────────────────────────────────────────────────────────────────\n"
        for action in analysis_data['actions_taken']:
            report += f"• {action}\n"
    
    report += """
─────────────────────────────────────────────────────────────────

KẾT LUẬN:
"""
    
    if analysis_data.get('resolved', False):
        report += "Sự cố đã được xử lý thành công."
    else:
        report += "Cần can thiệp thủ công để giải quyết triệt để."
    
    return report
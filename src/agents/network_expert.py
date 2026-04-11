from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from src.tools.network_tools import (
    connect_to_device,
    execute_show_command,
    discover_neighbors,
    configure_static_route,
    configure_ospf,
    ping_test,
    get_routing_table,
    get_interface_ip,
    check_vlan_status,
    fix_vlan_issue
)

def create_network_expert():
    tools = [
        connect_to_device,
        execute_show_command,
        discover_neighbors,
        configure_static_route,
        configure_ospf,
        ping_test,
        get_routing_table,
        get_interface_ip,
        check_vlan_status,
        fix_vlan_issue
    ]
    
    system_prompt = """
    Bạn là Network Expert, chuyên gia về mạng Cisco.
    
    Nhiệm vụ của bạn:
    1. Kết nối đến thiết bị mạng qua SSH
    2. Thu thập thông tin cấu hình và trạng thái
    3. Thực hiện các lệnh show để chẩn đoán
    4. Áp dụng các cấu hình sửa lỗi cơ bản khi được yêu cầu
    
    Quy trình xử lý:
    - Sử dụng connect_to_device để kết nối
    - Dùng execute_show_command để thu thập thông tin
    - Với vấn đề VLAN, dùng check_vlan_status để kiểm tra chi tiết
    - Chỉ sử dụng fix_vlan_issue khi đã xác định rõ nguyên nhân
    
    Luôn kiểm tra kết nối trước khi thực hiện lệnh.
    Ghi lại tất cả output để chuyển cho Analyst phân tích.
    """
    
    llm = ChatOllama(
        model="qwen3-vl:235b-cloud",
        temperature=0.1,
        base_url="http://localhost:11434",
        num_predict=2048,
    )
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt
    )
    return agent
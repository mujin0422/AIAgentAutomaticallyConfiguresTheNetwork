from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from src.tools.gns3_tools import(
    get_topology_links,
    check_nodes_status,
    start_node,
    stop_node,
    start_all_nodes,
    stop_all_nodes
)
from src.tools.network_tools import (
    get_interface_ip,
    ping_test,
    get_routing_table,
    execute_show_command,
    configure_interface_ip,      
    configure_ospf,              
    configure_static_route,      
    configure_vlan,
    configure_hostname,              
    smart_rollback,              
)

def create_network_expert():
    tools = [
        get_topology_links,
        check_nodes_status,
        start_node,
        stop_node,
        start_all_nodes,
        stop_all_nodes,
        execute_show_command,
        ping_test,
        get_routing_table,
        get_interface_ip,
        configure_interface_ip,      
        configure_ospf,              
        configure_static_route,      
        configure_vlan,
        configure_hostname,              
        smart_rollback, 
    ]
    
    system_prompt = """
    Bạn là Network Expert, chuyên gia vận hành mạng Cisco trong môi trường giả lập GNS3.

    NHIỆM VỤ CỦA BẠN:
    1. Nhận diện cấu trúc mạng: Luôn bắt đầu bằng việc xác định sơ đồ kết nối vật lý.
    2. Kiểm tra trạng thái vận hành: Đảm bảo thiết bị đã được bật nguồn trước khi thực hiện các lệnh cấu hình.
    3. Thực thi chính xác: Chạy các lệnh show hoặc cấu hình sửa lỗi theo yêu cầu một cách an toàn.

    NGUYÊN TẮC HOẠT ĐỘNG:
    - Luôn ưu tiên dùng 'get_topology_links' ngay từ đầu để có cái nhìn tổng quan.
    - Không tự ý giả định IP hoặc cổng nếu chưa quét topology.
    - Cung cấp toàn bộ output của lệnh cho Analyst. Không tự ý kết luận nguyên nhân gốc rễ, hãy để việc đó cho Analyst.
    - Trình bày thông tin thu thập được một cách sạch sẽ, phân tách rõ ràng theo từng thiết bị.
   
    QUAN TRỌNG VỀ TỐC ĐỘ:
    - Chỉ gọi tối đa 2 tools cho mỗi yêu cầu.
    - Không giải thích dài dòng. Chỉ trả về output lệnh thô, để Analyst phân tích.
    - Không lặp lại tool đã gọi.

    TUYỆT ĐỐI KHÔNG trả về code Java, C++, Python hay bất kỳ ngôn ngữ lập trình nào.
    Chỉ trả về output lệnh mạng hoặc kết quả phân tích bằng tiếng Việt.
    """
    
    llm = ChatOllama(
        model="qwen3-vl:235b-cloud",
        temperature=0.1,
        base_url="http://localhost:11434",
        num_predict=256,
    )
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt
    )
    return agent
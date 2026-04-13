from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.graph.state import NetworkState
from src.agents.supervisor import SupervisorAgent
from src.agents.network_expert import create_network_expert
from src.agents.analyst import create_analyst

def extract_network_data(state: NetworkState):
    """
    Node trung gian: Trích xuất nội dung từ ToolMessages vào trường command_outputs
    giúp Supervisor nhận diện được dữ liệu đã được thu thập.
    """
    messages = state.get("messages", [])
    new_outputs = state.get("command_outputs", {}).copy()
    
    # Duyệt ngược tin nhắn để lấy các output mới nhất từ các tool
    for msg in reversed(messages):
        if msg.type == "tool":
            tool_name = getattr(msg, 'name', 'unknown_tool')
            new_outputs[tool_name] = msg.content
        elif msg.type == "ai" and not getattr(msg, 'tool_calls', None):
            # Nếu gặp tin nhắn AI bình thường thì dừng lại (đã hết lượt tool hiện tại)
            break
            
    return {
        "command_outputs": new_outputs,
        "current_phase": "collected" if new_outputs else "start"
    }

def after_analyst(state: NetworkState):
    """
    Node xử lý sau khi Analyst phản hồi: 
    Lưu nội dung phân tích vào final_report để main.py có thể hiển thị.
    """
    messages = state.get("messages", [])
    last_content = messages[-1].content if messages else ""
    
    return {
        "analysis_results": {"status": "completed"}, 
        "current_phase": "analyzed",
        "final_report": last_content # Chuyển câu trả lời của Agent thành báo cáo chính thức
    }

def create_network_assistant_graph():
    # Khởi tạo các thành phần
    supervisor = SupervisorAgent()
    network_expert = create_network_expert()
    analyst = create_analyst()

    # Khởi tạo đồ thị với NetworkState
    builder = StateGraph(NetworkState)

    # Định nghĩa các Node
    builder.add_node("supervisor", supervisor.route)
    builder.add_node("network_expert", network_expert)
    builder.add_node("extract_data", extract_network_data)
    builder.add_node("analyst", analyst)
    builder.add_node("after_analyst", after_analyst)

    # Thiết lập luồng chạy (Edges)
    builder.add_edge(START, "supervisor")

    # Luồng Thu thập: Expert -> Extract -> Quay lại Supervisor kiểm tra
    builder.add_edge("network_expert", "extract_data")
    builder.add_edge("extract_data", "supervisor")

    # Luồng Phân tích: Analyst -> After Analyst (lưu report) -> Quay lại Supervisor để END
    builder.add_edge("analyst", "after_analyst")
    builder.add_edge("after_analyst", "supervisor")

    # Biên dịch đồ thị với bộ nhớ checkpoint
    graph = builder.compile(checkpointer=MemorySaver())

    return graph


# 1. Phân tích nguyên nhân gốc rễ
# Nguyên nhân 1: Agent không tự cập nhật Dictionary: Bạn đang dùng create_react_agent. Khi Agent này chạy các tool (như connect_to_device), kết quả trả về sẽ được LangGraph lưu vào danh sách messages dưới dạng các ToolMessage. Nó không tự động bóc tách kết quả đó để điền vào trường command_outputs hay interface_status trong NetworkState của bạn.
# Nguyên nhân 2: Supervisor bị "mù" thông tin: Trong file supervisor.py (phiên bản mới), Supervisor kiểm tra if not state.get("command_outputs"). Vì trường này luôn trống (do lý do 1), Supervisor mặc định hiểu là "chưa có dữ liệu" và tiếp tục gửi yêu cầu sang network_expert.
# Nguyên nhân 3: Vòng lặp: Supervisor -> network_expert (trả về tin nhắn) -> Supervisor (thấy dict vẫn trống) -> network_expert...
# ==> Chúng ta sẽ tạo một node trung gian để "bóc" dữ liệu từ tin nhắn của Agent và đưa vào State, đồng thời cập nhật Supervisor để điều hướng dựa trên lịch sử tin nhắn.

# from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.memory import MemorySaver
# from src.graph.state import NetworkState
# from src.agents.supervisor import SupervisorAgent
# from src.agents.network_expert import create_network_expert
# from src.agents.analyst import create_analyst

# def create_network_assistant_graph():
#     supervisor = SupervisorAgent()
#     network_expert = create_network_expert()
#     analyst = create_analyst()

#     builder = StateGraph(NetworkState)

#     # Thêm các node
#     builder.add_node("supervisor", supervisor.route)
#     builder.add_node("network_expert", network_expert)
#     builder.add_node("analyst", analyst)

#     # Định nghĩa luồng chạy
#     builder.add_edge(START, "supervisor")

#     # network_expert chạy xong luôn quay về supervisor để check state
#     builder.add_edge("network_expert", "supervisor")

#     # analyst chạy xong, ta cập nhật state đánh dấu đã phân tích rồi quay về supervisor
#     def after_analyst_node(state: NetworkState):
#         # Lấy nội dung tin nhắn cuối cùng để làm kết quả nếu cần
#         return {
#             "analysis_results": {"status": "completed"}, 
#             "current_phase": "analyzed"
#         }
    
#     builder.add_node("after_analyst", after_analyst_node)
#     builder.add_edge("analyst", "after_analyst")
#     builder.add_edge("after_analyst", "supervisor")

#     # Lưu ý: Không cần builder.add_conditional_edges cho supervisor 
#     # vì supervisor.route đã trả về Command(goto=...)

#     graph = builder.compile(checkpointer=MemorySaver())
#     return graph
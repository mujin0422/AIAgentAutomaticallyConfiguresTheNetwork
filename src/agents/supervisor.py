from typing import Literal
from src.graph.state import NetworkState
from langgraph.types import Command
from langgraph.graph import END

class SupervisorAgent:
    def route(self, state: NetworkState):
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        # 1. KIỂM TRA ĐIỂM DỪNG: Nếu Analyst đã trả lời hoặc phase đã xong
        if state.get("current_phase") == "analyzed":
             # Nếu tin nhắn cuối là từ AI và không yêu cầu gọi tool nữa -> Xong
            if last_message and last_message.type == "ai" and not getattr(last_message, 'tool_calls', None):
                print("\033[95m[SUPERVISOR] Phân tích hoàn tất. Kết thúc workflow.\033[0m")
                return Command(goto=END, update={"current_phase": "finished"})

        # 2. KIỂM TRA DỮ LIỆU: Nếu chưa có bất kỳ tool message nào trong lịch sử HOẶC command_outputs trống
        has_tool_output = any(msg.type == "tool" for msg in messages)
        
        if not has_tool_output and not state.get("command_outputs"):
            print("\033[95m[SUPERVISOR] Đang thu thập dữ liệu thiết bị từ ➤  NETWORK EXPERT ...\033[0m")
            return Command(
                goto="network_expert",
                update={"current_phase": "collecting"}
            )
        
        # 3. CHUYỂN SANG PHÂN TÍCH: Nếu đã có dữ liệu nhưng chưa phân tích
        if state.get("current_phase") != "analyzed":
            print("\033[95m[SUPERVISOR] Đã có dữ liệu. Thực hiện phân tích với ➤  ANALYST ...\033[0m")
            return Command(
                goto="analyst",
                update={"current_phase": "analyzing"}
            )

        return Command(goto=END)
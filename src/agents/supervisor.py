from typing import Literal
from src.graph.state import NetworkState
from langgraph.types import Command
from langgraph.graph import END

class SupervisorAgent:
    def route(self, state: NetworkState):
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        # 1. KIỂM TRA ĐIỂM DỪNG: Nếu Analyst đã trả lời xong
        if state.get("current_phase") == "analyzed":
            if last_message and last_message.type == "ai" and not getattr(last_message, 'tool_calls', None):
                print("\033[95m[SUPERVISOR] Phân tích hoàn tất. Kết thúc workflow.\033[0m")
                return Command(goto=END, update={"current_phase": "finished"})

        # 2. XỬ LÝ NGOẠI LỆ: EXPERT HỎI LẠI VÌ THIẾU THÔNG TIN
        # Nếu tin nhắn cuối là từ AI (Expert) và nó KHÔNG dùng tool (Tức là nó đang hỏi/từ chối)
        if state.get("current_phase") in ["start", "collecting"]:
            if last_message and last_message.type == "ai" and not getattr(last_message, 'tool_calls', None):
                print("\033[95m[SUPERVISOR] Expert đang yêu cầu thêm thông tin. Chuyển sang ➤ ANALYST ...\033[0m")
                return Command(goto="analyst", update={"current_phase": "analyzing"})

        # 3. KIỂM TRA DỮ LIỆU BÌNH THƯỜNG
        has_tool_output = any(msg.type == "tool" for msg in messages)
        
        if not has_tool_output and not state.get("command_outputs"):
            print("\033[95m[SUPERVISOR] Đang thu thập dữ liệu thiết bị từ ➤  NETWORK EXPERT ...\033[0m")
            return Command(
                goto="network_expert",
                update={"current_phase": "collecting"}
            )
        
        # 4. CHUYỂN SANG PHÂN TÍCH
        if state.get("current_phase") != "analyzed":
            print("\033[95m[SUPERVISOR] Đã có dữ liệu. Thực hiện phân tích với ➤  ANALYST ...\033[0m")
            return Command(
                goto="analyst",
                update={"current_phase": "analyzing"}
            )

        return Command(goto=END)
from typing import Literal
from langchain_ollama import ChatOllama
from src.graph.state import NetworkState

class SupervisorAgent:
    def __init__(self, model: str = "qwen3-vl:235b-cloud"):
        self.llm = ChatOllama(
            model=model,
            temperature=0.1,
            base_url="http://localhost:11434",
            num_predict=1024,
        )
        self.step_count = 0
    
    def should_continue(self, state: NetworkState) -> Literal["network_expert", "analyst", "__end__"]:
        self.step_count += 1
        
        print(f"\n\n📌 STEP {self.step_count}:")
        
        # KIỂM TRA analysis_results
        if state.get("analysis_results"):
            print("   Đã có kết quả phân tích, kết thúc workflow")
            return "__end__"
        
        # Kiểm tra current_phase
        if state.get("current_phase") == "analyzed":
            print("   Đã phân tích xong, kết thúc workflow")
            return "__end__"
        
        # Bước 1: Gọi network_expert
        if self.step_count == 1:
            print("   Gọi network_expert để thu thập dữ liệu")
            return "network_expert"
        
        # Bước 2: Gọi analyst
        if self.step_count == 2:
            print("   Gọi analyst để phân tích kết quả")
            return "analyst"
        
        # Nếu đã chạy quá 3 bước, kết thúc
        if self.step_count > 3:
            print("   Quá số bước, kết thúc workflow")
            return "__end__"
        
        return "__end__"
    
    def route(self, state: NetworkState):
        goto = self.should_continue(state)
        
        from langgraph.types import Command
        
        if goto == "__end__":
            return Command(goto=goto, update={"current_phase": "finished"})
        
        return Command(
            update={
                "current_phase": "routing",
                "next_agent": goto
            },
            goto=goto
        )
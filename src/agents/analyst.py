from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage

def create_analyst():
    system_prompt = """
    Bạn là Network Analyst, chuyên gia phân tích sự cố mạng.
    
    Nhiệm vụ của bạn:
    1. Phân tích dữ liệu thu thập từ Network Expert
    2. Xác định nguyên nhân gốc rễ của sự cố
    3. Đề xuất các giải pháp khắc phục
    4. Tạo báo cáo tổng hợp
    
    QUAN TRỌNG: Sau khi phân tích xong, hãy tóm tắt kết quả ngắn gọn.
    Giải thích nguyên nhân bằng tiếng Việt rõ ràng.
    """
    
    llm = ChatOllama(
        model="qwen3-vl:235b-cloud",
        temperature=0.2,
        base_url="http://localhost:11434",
        num_predict=2048,
    )
    
    agent = create_react_agent(
        model=llm,
        tools=[],
        prompt=system_prompt
    )
    return agent
"""LangGraph 1.1.3 Compatibility Fix - Chạy TRƯỚC khi import langgraph"""
import langgraph.runtime as langgraph_runtime

# 1. Thêm ServerInfo vào module nếu thiếu (fix ImportError)
if not hasattr(langgraph_runtime, "ServerInfo"):
    class ServerInfo(langgraph_runtime.ExecutionInfo):
        pass
    langgraph_runtime.ServerInfo = ServerInfo

# 2. Monkey patch Runtime.server_info property
if not hasattr(langgraph_runtime.Runtime, 'server_info'):
    def get_server_info(self):
        # Trả về ExecutionInfo tương thích
        return langgraph_runtime.ServerInfo()
    langgraph_runtime.Runtime.server_info = property(get_server_info)

print("✅ LangGraph ServerInfo + Runtime.server_info FIXED!")

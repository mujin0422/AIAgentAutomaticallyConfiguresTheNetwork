from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState

class DeviceConnection(BaseModel): 
    """Thông tin kết nối thiết bị"""
    hostname: str = Field(default="")
    device_type: str = Field(default="cisco_ios")
    username: str = Field(default="")
    password: str = Field(default="")
    secret: Optional[str] = Field(default=None)
    port: int = Field(default=22)

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        extra = "ignore"

class NetworkState(MessagesState):
    """State cho network agent"""
    # Thông tin thiết bị
    target_device: Optional[DeviceConnection] = Field(default=None)
    devices: List[DeviceConnection] = Field(default_factory=list)
    
    # Dữ liệu thu thập → Output của network_expert
    command_outputs: Dict[str, str] = Field(default_factory=dict) # Lưu output của từng command
    running_config: Optional[str] = Field(default=None) # Lưu cấu hình đang chạy
    interface_status: Dict[str, Any] = Field(default_factory=dict) # Lưu trạng thái các interface
    vlan_info: Dict[str, Any] = Field(default_factory=dict) # Lưu thông tin VLAN
    error_logs: List[str] = Field(default_factory=list) # Lưu log lỗi nếu có
    
    # Phân tích → Output của analyst
    current_phase: str = Field(default="start")
    analysis_results: Dict[str, Any] = Field(default_factory=dict)
    root_cause: Optional[str] = Field(default=None)
    recommendations: List[str] = Field(default_factory=list)
    
    # Hành động → Dùng cho automation (fix lỗi, config lại)
    actions_taken: List[str] = Field(default_factory=list) # Lưu các hành động đã thực hiện
    pending_actions: List[str] = Field(default_factory=list) # Lưu các hành động đang chờ thực hiện (nếu có)
    
    # Kết quả → Kết quả cuối cùng cho user
    final_report: Optional[str] = Field(default=None)
    incident_resolved: bool = Field(default=False)
    
    # Điều khiển luồng → dùng cùng với: Literal["network_expert", "analyst", "__end__"]
    current_phase: str = Field(default="start") # start → collecting → analyzing → recommending → acting → finished
    next_agent: Optional[str] = Field(default="__end__") # "network_expert", "analyst", None (khi đã xong)

class Incident(BaseModel):
    """Mô hình sự cố"""
    id: str = Field(default="")
    description: str = Field(default="")
    severity: str = Field(default="")
    timestamp: str = Field(default="")
    status: str = Field(default="")
    affected_devices: List[str] = Field(default_factory=list)
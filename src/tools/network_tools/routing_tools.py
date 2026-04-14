from typing import Dict, Any, Optional
from langchain_core.tools import tool
from netmiko import ConnectHandler
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from src.tools.network_tools import get_default_device_config, get_ssh_params
# Không cần import parser functions
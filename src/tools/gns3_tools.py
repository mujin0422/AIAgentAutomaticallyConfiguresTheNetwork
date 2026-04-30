import requests
from langchain_core.tools import tool

#GNS3_IP = "172.20.10.3"
#GNS3_IP = "192.168.2.5"
GNS3_IP = "127.0.0.1"
GNS3_PORT = "3080"
BASE_URL = f"http://{GNS3_IP}:{GNS3_PORT}/v2"
PROJECT_ID = "cc92102e-89e3-4f2d-8e66-47268c496baa"

@tool
def get_topology_links() -> str:
    """
    Lấy sơ đồ nối dây thực tế giữa các Router trong GNS3.
    Dùng công cụ này để biết cổng nào của R1 nối với cổng nào của R2.
    """
    url = f"{BASE_URL}/projects/{PROJECT_ID}/links"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        links = response.json()
        
        if not links:
            return "Không tìm thấy kết nối nào."

        output = "SƠ ĐỒ KẾT NỐI (TOPOLOGY):\n"
        for link in links:
            n = link['nodes']
            # Trích xuất label để lấy tên thiết bị (R1, R2...)
            node_a = n[0].get('label', {}).get('text', n[0]['node_id'][:5])
            node_b = n[1].get('label', {}).get('text', n[1]['node_id'][:5])
            output += f"- {node_a} (Port {n[0]['port_number']}) <---> {node_b} (Port {n[1]['port_number']})\n"
        return output
    except Exception as e:
        return f"Lỗi lấy links: {str(e)}"

@tool
def check_nodes_status() -> str:
    """
    Kiểm tra trạng thái (đang chạy hay đang tắt) của các thiết bị trong GNS3.
    """
    url = f"{BASE_URL}/projects/{PROJECT_ID}/nodes"
    try:
        response = requests.get(url)
        response.raise_for_status()
        nodes = response.json()
        
        output = "TRẠNG THÁI THIẾT BỊ:\n"
        for node in nodes:
            output += f"- {node['name']}: {node['status']}\n"
        return output
    except Exception as e:
        return f"Lỗi lấy trạng thái node: {str(e)}"
    
@tool
def start_node(node_name: str) -> str:
    """
    Sử dụng công cụ này để bật nguồn (start) một thiết bị trong GNS3 khi nó đang ở trạng thái 'stopped'.
    Tham số: node_name (tên của thiết bị, ví dụ: 'R3').
    """
    # Đầu tiên cần lấy ID của node từ tên node
    url_nodes = f"{BASE_URL}/projects/{PROJECT_ID}/nodes"
    try:
        nodes_resp = requests.get(url_nodes)
        nodes = nodes_resp.json()
        node_id = next((n['node_id'] for n in nodes if n['name'] == node_name), None)
        
        if not node_id:
            return f"Không tìm thấy thiết bị có tên {node_name} để bật."

        # Gửi lệnh start
        url_start = f"{BASE_URL}/projects/{PROJECT_ID}/nodes/{node_id}/start"
        response = requests.post(url_start)
        if response.status_code in [200, 201, 204]:
            return f"Đã gửi lệnh khởi động thiết bị {node_name} thành công. Vui lòng đợi vài giây để thiết bị khởi động xong."
        else:
            return f"Không thể bật thiết bị {node_name}. Lỗi: {response.text}"
    except Exception as e:
        return f"Lỗi hệ thống khi cố gắng bật thiết bị: {str(e)}"
    
@tool
def stop_node(node_name: str)-> str:
    """
    Sử dụng công cụ này để tắt (stop) một thiết bị trong GNS3 khi nó đang ở trạng thái 'started'.
    Tham số: node_name (tên của thiết bị, ví dụ: 'R3').
    """
    url_nodes = f"{BASE_URL}/projects/{PROJECT_ID}/nodes"
    try:
        nodes_resp = requests.get(url_nodes)
        nodes = nodes_resp.json()
        node_id = next((n['node_id'] for n in nodes if n['name'] == node_name), None)
        if not node_id:
            return f"Không tìm thấy thiết bị có tên {node_name} để tắt."
        
        # Gửi lệnh stop
        url_stop = f"{BASE_URL}/projects/{PROJECT_ID}/nodes/{node_id}/stop"
        response = requests.post(url_stop)
        if response.status_code in [200, 201, 204]:
            return f"Đã gửi lệnh tắt thiết bị {node_name} thành công. Vui lòng đợi vài giây để thiết bị tắt hoàn toàn."
        else:
            return f"Không thể tắt thiết bị {node_name}. Lỗi: {response.text}"
    except Exception as e:
        return f"Lỗi hệ thống khi cố gắng tắt thiết bị: {str(e)}"
    
@tool
def start_all_nodes() -> str:
    """
    Bật TẤT CẢ các thiết bị đang tắt trong dự án GNS3.
    Sử dụng khi người dùng yêu cầu bật toàn bộ thiết bị (ví dụ: "bật tất cả", "start all").
    """
    url_nodes = f"{BASE_URL}/projects/{PROJECT_ID}/nodes"
    try:
        nodes_resp = requests.get(url_nodes)
        nodes_resp.raise_for_status()
        nodes = nodes_resp.json()

        stopped_nodes = [n for n in nodes if n.get('status') == 'stopped']  
        if not stopped_nodes:
            return "Không có thiết bị nào đang tắt để bật."
        
        results = []
        for node in stopped_nodes:
            node_id = node['node_id']
            node_name = node['name']
            url_start = f"{BASE_URL}/projects/{PROJECT_ID}/nodes/{node_id}/start"
            try:
                response = requests.post(url_start)
                if response.status_code in [200,201,204]:
                    results.append(f"Đã bật {node_name}")
                else:
                    results.append(f"Không thể bật {node_name}: {response.text}")
            except Exception as e:
                results.append(f"Lỗi khi bật {node_name}: {str(e)}")
        return "KẾT QUẢ BẬT TẤT CẢ THIẾT BỊ:\n" + "\n".join(results)
    except Exception as e:
        return f"Lỗi hệ thống khi cố gắng bật tất cả thiết bị: {str(e)}"
    
@tool
def stop_all_nodes() -> str:
    """
    Tắt TẤT CẢ các thiết bị đang chạy trong dự án GNS3.
    Sử dụng khi người dùng yêu cầu tắt toàn bộ thiết bị (ví dụ: "tắt tất cả", "stop all").
    """
    url_nodes = f"{BASE_URL}/projects/{PROJECT_ID}/nodes"
    try:
        nodes_resp = requests.get(url_nodes)
        nodes_resp.raise_for_status()
        nodes = nodes_resp.json()

        running_nodes = [n for n in nodes if n.get('status') == 'started']
        if not running_nodes:
            return "Không có thiết bị nào đang chạy để tắt."
        
        results = []
        for node in running_nodes:
            node_id = node['node_id']
            node_name = node['name']
            url_stop = f"{BASE_URL}/projects/{PROJECT_ID}/nodes/{node_id}/stop"
            try:
                response = requests.post(url_stop)
                if response.status_code in [200, 201, 204]:
                    results.append(f"Đã tắt {node_name}")
                else:
                    results.append(f"Không thể tắt {node_name}: {response.text}")
            except Exception as e:
                results.append(f"Lỗi khi tắt {node_name}: {str(e)}")
        return "KẾT QUẢ TẮT TẤT CẢ THIẾT BỊ:\n" + "\n".join(results)
    except Exception as e:
        return f"Lỗi hệ thống khi cố gắng tắt tất cả thiết bị: {str(e)}"
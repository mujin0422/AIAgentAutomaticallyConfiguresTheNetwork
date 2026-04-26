import customtkinter as ctk
import threading
import time
import json  # Thêm thư viện json để xử lý raw data
from PIL import Image
from langchain_core.messages import HumanMessage
from src.graph.state import NetworkState
from src.graph.workflow import createNetworkAssistantGraph
from src.main import check_gns3_connectivity, loadDeviceConfig, createDeviceConnection

# --- CẤU HÌNH GIAO DIỆN ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class NetworkAssistantApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Network AI Assistant")
        self.geometry("750x900")
        self.configure(fg_color="#0F0F0F") 
        self.graph = None
        self.device_obj = None
        self.thread_id = f"session_{int(time.time())}"
        self.loading_container = None
        self.setup_ui()
        self.init_backend()

    def setup_ui(self):
        # 1. Khung cuộn hiển thị lịch sử chat
        self.chat_display = ctk.CTkScrollableFrame(
            self, 
            fg_color="#0F0F0F", # Nền đen
            scrollbar_button_color="#4a4a4a"
        )
        self.chat_display.pack(padx=20, pady=(20, 10), fill="both", expand=True)

        # 2. Khung chứa ô nhập liệu dưới cùng
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(padx=20, pady=(0, 20), fill="x", side="bottom")

        # 2.1. Ô nhập liệu bo góc mềm mại
        self.entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Nhập yêu cầu kiểm tra hệ thống mạng...", 
            font=("Roboto", 15),
            height=40,
            corner_radius=20,
            border_width=1,
            border_color="#333333",
            fg_color="#1E1E1E", # Nền xám đậm cho ô nhập liệu
            text_color="#FFFFFF" # Chữ trắng
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", lambda event: self.send_message())

        # 2.2. Nút gửi với icon (nếu có), nền xám đen, hover sáng hơn)
        try:
            icon_image = ctk.CTkImage(
                light_image=Image.open("images/icon/send.png"),
                dark_image=Image.open("images/icon/send.png"),
                size=(22, 22)
            )
        except Exception as e:
            print(f"Không thể tải ảnh icon: {e}")
            icon_image = None 

        self.send_btn = ctk.CTkButton(
            self.input_frame, 
            text="", 
            image=icon_image, 
            command=self.send_message, 
            width=40, 
            height=40,
            fg_color="#0F0F0F", 
            hover_color="#1E1E1E"
        )
        self.send_btn.pack(side="right")

    def add_message(self, sender, text):
        """Hàm vẽ từng bong bóng chat dựa vào người gửi"""
        container = ctk.CTkFrame(self.chat_display, fg_color="transparent")
        container.pack(fill="x", pady=10, padx=5)

        if sender == "user":
            # Tin nhắn User: Căn phải, nền xám tối, chữ trắng
            bubble = ctk.CTkFrame(container, fg_color="#2B2B2B", corner_radius=20)
            bubble.pack(side="right", padx=(50, 5))
            lbl = ctk.CTkLabel(bubble, text=text, font=("Roboto", 15), text_color="#FFFFFF", wraplength=450, justify="left")
            lbl.pack(padx=20, pady=10)

        elif sender == "ai":
            # Tin nhắn AI: Căn trái, có icon ✨, chữ trắng
            avatar = ctk.CTkLabel(container, text="✨", font=("Roboto", 22), text_color="#1a73e8")
            avatar.pack(side="left", anchor="nw", padx=(5, 10), pady=5)
            
            bubble = ctk.CTkFrame(container, fg_color="#1E1E1E", corner_radius=20)
            bubble.pack(side="left", fill="both", expand=True, padx=(0, 50))
            
            # Tính toán chiều cao chính xác và rộng rãi hơn
            lines = text.split('\n')
            total_lines = 0
            for line in lines:
                if line.strip() == "":
                    total_lines += 1
                else:
                    total_lines += (len(line) // 55) + 1 
            
            box_height = total_lines * 24 + 15 
            
            box = ctk.CTkTextbox(bubble, font=("Roboto", 15), fg_color="transparent", text_color="#FFFFFF", wrap="word", height=box_height)
            box.pack(fill="both", expand=True, padx=15, pady=10)
            box.insert("1.0", text)
            box.configure(state="disabled") # Khóa để không bị sửa chữ

        elif sender == "system":
            # Thông báo hệ thống: Căn giữa, chữ xám, nghiêng
            lbl = ctk.CTkLabel(container, text=text, font=("Roboto", 15, "italic"), text_color="#888888")
            lbl.pack(anchor="center")

        # Cập nhật và cuộn xuống dưới cùng
        self.update_idletasks()
        self.chat_display._parent_canvas.yview_moveto(1.0)

    def show_loading(self):
        """Hiển thị trạng thái đang xử lý"""
        self.loading_container = ctk.CTkFrame(self.chat_display, fg_color="transparent")
        self.loading_container.pack(fill="x", pady=10, padx=5)
        
        avatar = ctk.CTkLabel(self.loading_container, text="✨", font=("Roboto", 22), text_color="#1a73e8")
        avatar.pack(side="left", anchor="nw", padx=(5, 10))
        
        lbl = ctk.CTkLabel(self.loading_container, text="Đang quét sơ đồ và phân tích...", font=("Roboto", 15, "italic"), text_color="#888888")
        lbl.pack(side="left", anchor="w")
        
        self.update_idletasks()
        self.chat_display._parent_canvas.yview_moveto(1.0)

    def hide_loading(self):
        """Xóa trạng thái đang xử lý"""
        if self.loading_container:
            self.loading_container.destroy()
            self.loading_container = None

    def init_backend(self):
        self.add_message("system", "Đang khởi tạo kết nối GNS3 và nạp Agent...")
        threading.Thread(target=self._init_task, daemon=True).start()

    def _init_task(self):
        if check_gns3_connectivity():
            config = loadDeviceConfig()
            if config:
                self.device_obj = createDeviceConnection(config)
                self.graph = createNetworkAssistantGraph()
                self.after(0, lambda: self.add_message("system", "Khởi tạo thành công! Sẵn sàng hỗ trợ bạn."))
            else:
                self.after(0, lambda: self.add_message("system", "Lỗi: Không thể tải cấu hình thiết bị từ devices.yaml."))
        else:
            self.after(0, lambda: self.add_message("system", "Lỗi: Không thể kết nối tới GNS3 Server!"))

    def send_message(self):
        user_text = self.entry.get().strip()
        if not user_text or not self.graph:
            return

        self.entry.delete(0, "end")
        self.send_btn.configure(state="disabled")
        
        # Thêm tin nhắn user vào UI
        self.add_message("user", user_text)
        self.show_loading()

        threading.Thread(target=self._process_ai, args=(user_text,), daemon=True).start()

    def _process_ai(self, user_text):
        initial_state = NetworkState(
            messages=[HumanMessage(content=user_text)],
            target_device=self.device_obj,
            devices=[self.device_obj]
        )
        config = {"configurable": {"thread_id": self.thread_id}}

        final_response = ""
        log_text = ""

        for chunk in self.graph.stream(initial_state, config):
            if "extract_data" in chunk:
                outputs = chunk["extract_data"].get("command_outputs", {})
                
                # Cập nhật GUI log (như cũ)
                for tool_name in outputs:
                    log_text += f"Đã chạy: {tool_name}\n"

                # --- BẮT ĐẦU IN RAW DATA LÊN TERMINAL ---
                if outputs:
                    content_width = 120
                    frame_width = content_width + 4
                    
                    print("\n\t\033[96m" + "╔" + "═"*(frame_width-2) + "╗" + "\033[0m")
                    
                    title = "║ [RAW DATA] KẾT QUẢ THỰC THI TỪ THIẾT BỊ"
                    print("\t\033[96m" + title + " "*(frame_width - len(title) - 1) + "║\033[0m")
                    print("\t\033[96m" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")
                    
                    tool_count = len(outputs)
                    current_tool = 0
                    
                    for tool_name, result in outputs.items():
                        current_tool += 1
                        display_text = str(result)
                        try:
                            parsed_data = json.loads(display_text)
                            if isinstance(parsed_data, dict):
                                if parsed_data.get("success") is False:
                                    display_text = f"LỖI: {parsed_data.get('error', 'Không rõ nguyên nhân')}"
                                elif "output" in parsed_data:
                                    display_text = str(parsed_data["output"])
                        except Exception:
                            pass 

                        tool_line = f"Tool đã dùng: {tool_name}"
                        print("\t\033[96m║ \033[93m" + tool_line.ljust(content_width) + " \033[96m║\033[0m")
                        print("\t\033[96m║ \033[90m" + "Output:".ljust(content_width) + " \033[96m║\033[0m")
                        
                        for line in display_text.split('\n'):
                            safe_line = line.replace('\r', '')[:content_width] 
                            print("\t\033[96m║ \033[90m" + safe_line.ljust(content_width) + " \033[96m║\033[0m")
                        
                        if current_tool < tool_count:
                            print("\t\033[96m" + "╠" + "═"*(frame_width-2) + "╣" + "\033[0m")

                    print("\t\033[96m" + "╚" + "═"*(frame_width-2) + "╝" + "\033[0m\n")
                # --- KẾT THÚC IN RAW DATA LÊN TERMINAL ---

            if "analyst" in chunk:
                msg = chunk["analyst"].get("messages", [])[-1]
                if hasattr(msg, 'content') and msg.content:
                    final_response = msg.content

        # Ghép log (nếu có) vào phía trên câu trả lời chính thức
        if log_text:
            combined_response = f"[Nhật ký xử lý]\n{log_text.strip()}\n\n---\n\n{final_response}"
        else:
            combined_response = final_response

        self.after(0, self._update_ai_response, combined_response)

    def _update_ai_response(self, combined_response):
        self.hide_loading()
        self.add_message("ai", combined_response)
        self.send_btn.configure(state="normal")

if __name__ == "__main__":
    app = NetworkAssistantApp()
    app.mainloop()
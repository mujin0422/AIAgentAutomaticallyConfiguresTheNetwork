import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class ConfigBackupManager:
    """Quản lý nhiều phiên bản backup cấu hình"""
    
    def __init__(self, backup_dir: str = "config_backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.index_file = self.backup_dir / "backup_index.json"
        self.load_index()
    
    def load_index(self):
        """Load index của tất cả backups"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
        else:
            self.index = {}
    
    def save_index(self):
        """Lưu index backups"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    def create_backup(self, hostname: str, config_type: str, content: str, 
                      description: str = "") -> str:
        """
        Tạo một bản backup mới
        
        Args:
            hostname: Tên thiết bị
            config_type: Loại config (interface, ospf, route, full)
            content: Nội dung config
            description: Mô tả thay đổi
        
        Returns:
            backup_id: ID của bản backup
        """
        timestamp = datetime.now()
        backup_id = f"{hostname}_{config_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Lưu nội dung backup
        backup_file = self.backup_dir / f"{backup_id}.txt"
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Lưu metadata
        if hostname not in self.index:
            self.index[hostname] = []
        
        backup_info = {
            "backup_id": backup_id,
            "hostname": hostname,
            "config_type": config_type,
            "timestamp": timestamp.isoformat(),
            "description": description,
            "file": str(backup_file),
            "size": len(content)
        }
        
        self.index[hostname].append(backup_info)
        self.save_index()
        
        return backup_id
    
    def get_backups(self, hostname: str, config_type: str = None) -> List[Dict]:
        """Lấy danh sách backups của một thiết bị"""
        if hostname not in self.index:
            return []
        
        backups = self.index[hostname]
        if config_type:
            backups = [b for b in backups if b["config_type"] == config_type]
        
        # Sắp xếp theo thời gian giảm dần (mới nhất lên đầu)
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def get_backup_content(self, backup_id: str) -> Optional[str]:
        """Đọc nội dung của một bản backup"""
        backup_file = self.backup_dir / f"{backup_id}.txt"
        if backup_file.exists():
            with open(backup_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def delete_backup(self, backup_id: str) -> bool:
        """Xóa một bản backup"""
        for hostname, backups in self.index.items():
            for i, backup in enumerate(backups):
                if backup["backup_id"] == backup_id:
                    # Xóa file
                    backup_file = self.backup_dir / f"{backup_id}.txt"
                    if backup_file.exists():
                        backup_file.unlink()
                    # Xóa khỏi index
                    self.index[hostname].pop(i)
                    self.save_index()
                    return True
        return False
    
    def list_backups_pretty(self, hostname: str = None) -> str:
        """Hiển thị danh sách backups dạng đẹp"""
        result = []
        result.append("\n DANH SÁCH BACKUP CẤU HÌNH\n")
        result.append("─" * 80)
        
        devices = [hostname] if hostname else self.index.keys()
        
        for device in devices:
            if device not in self.index:
                continue
            
            result.append(f"\n  Thiết bị: {device}")
            result.append("─" * 40)
            
            for backup in self.get_backups(device):
                timestamp = datetime.fromisoformat(backup["timestamp"])
                result.append(
                    f"  📄 [{backup['backup_id']}]"
                )
                result.append(f"      Thời gian: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                result.append(f"      Loại: {backup['config_type']}")
                result.append(f"      Mô tả: {backup['description'] or 'Không có mô tả'}")
                result.append(f"      Kích thước: {backup['size']} bytes")
                result.append("")
        
        return "\n".join(result)
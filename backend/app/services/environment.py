"""探测环境变化备案业务规则：状态流转、撞单判定、照片附件与导出口径都收在这里。"""
from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.store import store

MODULE = "environment"
REQUIRED_FIELDS = ["所属站点", "干扰源类型", "发现时刻", "遮挡方位", "上报人"]
STATUS_ORDER = ["待核实", "已核实", "已整改", "已销号"]
CLOSED_STATUS = STATUS_ORDER[-1]

# 动作 -> (允许的前置状态, 目标状态, 执行时必须一并提交的字段)
ACTION_RULES: dict[str, tuple[str, str, str | None]] = {
    "核实": ("待核实", "已核实", "核实结论"),
    "整改": ("已核实", "已整改", "整改记录"),
    "销号": ("已整改", "已销号", None),
}

EXPORT_HEADER = ["备案编号", "所属站点", "干扰源类型", "发现时刻", "遮挡方位", "上报人", "核实结论", "整改记录", "备案状态", "重复上报次数"]

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "environment"
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
PHOTO_MAX_BYTES = 10 * 1024 * 1024

# 多人同时上报时编号分配与撞单判定要串行，避免并发下编号重复或漏判撞单。
_create_lock = threading.Lock()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class EnvironmentService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        station: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("备案编号", ""))]
        if station:
            rows = [row for row in rows if station in str(row.get("所属站点", ""))]
        if source_type:
            rows = [row for row in rows if source_type in str(row.get("干扰源类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        result = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            status = str(row.get("status", ""))
            if status in result:
                result[status] += 1
        result["total"] = len(rows)
        return result

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_conflict(self, station: str, source_type: str) -> dict[str, Any] | None:
        """同一站点同一干扰源只留一条在办备案；已销号的不再拦截新的上报。"""
        for row in store.rows(MODULE):
            if row.get("status") == CLOSED_STATUS:
                continue
            if row.get("所属站点") == station and row.get("干扰源类型") == source_type:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], dict[str, Any] | None]:
        """登记一条备案；撞单时不新建记录，返回撞上的那条并累加它的重复上报次数。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, None
        station = str(values.get("所属站点")).strip()
        source_type = str(values.get("干扰源类型")).strip()
        with _create_lock:
            conflict = self._find_conflict(station, source_type)
            if conflict is not None:
                conflict["重复上报次数"] = int(conflict.get("重复上报次数", 0)) + 1
                return None, [], conflict
            rows = store.rows(MODULE)
            entry: dict[str, Any] = {
                "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
                "备案编号": self._next_code(rows),
                "所属站点": station,
                "干扰源类型": source_type,
                "发现时刻": str(values.get("发现时刻")).strip(),
                "遮挡方位": str(values.get("遮挡方位")).strip(),
                "上报人": str(values.get("上报人")).strip(),
                "核实结论": "",
                "整改记录": "",
                "重复上报次数": 0,
                "登记时刻": _now(),
                "attachments": [],
                "status": STATUS_ORDER[0],
                "备案状态": STATUS_ORDER[0],
                "pending": True,
                "abnormal": False,
            }
            rows.append(entry)
        return entry, [], None

    @staticmethod
    def _next_code(rows: list[dict[str, Any]]) -> str:
        max_no = 0
        for row in rows:
            match = re.fullmatch(r"ENVI-(\d+)", str(row.get("备案编号", "")))
            if match:
                max_no = max(max_no, int(match.group(1)))
        return f"ENVI-{max_no + 1:04d}"

    def batch_create(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """多人同时上报：逐条处理、逐条给回执，单条失败不影响其他条。"""
        receipts: list[dict[str, Any]] = []
        for index, values in enumerate(reports, start=1):
            entry, missing, conflict = self.create_entry(values)
            if missing:
                receipts.append({
                    "序号": index,
                    "ok": False,
                    "message": f"缺少必填字段：{'、'.join(missing)}",
                    "备案编号": None,
                    "entry_id": None,
                })
            elif conflict is not None:
                receipts.append({
                    "序号": index,
                    "ok": False,
                    "message": f"与备案 {conflict['备案编号']}（{conflict['所属站点']}·{conflict['干扰源类型']}）撞单，已保留原备案并计入重复上报",
                    "备案编号": conflict["备案编号"],
                    "entry_id": conflict["id"],
                })
            else:
                receipts.append({
                    "序号": index,
                    "ok": True,
                    "message": f"备案 {entry['备案编号']} 已登记",
                    "备案编号": entry["备案编号"],
                    "entry_id": entry["id"],
                })
        return receipts

    def run_action(self, entry_id: int, action: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"备案 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于探测环境备案可执行范围"
        if entry.get("status") == CLOSED_STATUS:
            return None, f"备案 {entry.get('备案编号')} 已销号，不允许再{action}"
        expected, target, field = ACTION_RULES[action]
        if entry.get("status") != expected:
            return None, f"备案当前状态为「{entry.get('status')}」，不能执行{action}"
        if field is not None:
            content = str(values.get(field) or "").strip()
            if not content:
                return None, f"{field}缺失，不能执行{action}"
            entry[field] = content
        if action == "销号" and not str(entry.get("核实结论") or "").strip():
            return None, "核实结论缺失，不允许销号"
        entry["status"] = target
        entry["备案状态"] = target
        entry["pending"] = target != CLOSED_STATUS
        entry["abnormal"] = False
        return entry, f"备案 {entry.get('备案编号')} 已{action}"

    def add_attachment(self, entry_id: int, filename: str, content: bytes) -> tuple[dict[str, Any] | None, str]:
        """现场照片以文件形式落盘，备案上只记附件元信息。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"备案 {entry_id} 不存在或已归档"
        suffix = Path(filename).suffix.lower()
        if suffix not in PHOTO_SUFFIXES:
            return None, f"仅支持照片附件（{'、'.join(sorted(PHOTO_SUFFIXES))}），收到的是「{suffix or '无后缀'}」"
        if not content:
            return None, "附件内容为空，未留存"
        if len(content) > PHOTO_MAX_BYTES:
            return None, "照片超过 10MB，请压缩后再上传"
        stored = f"{uuid.uuid4().hex}{suffix}"
        folder = UPLOAD_DIR / str(entry_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / stored).write_bytes(content)
        record = {"filename": filename, "stored": stored, "size": len(content), "uploaded_at": _now()}
        entry.setdefault("attachments", []).append(record)
        return entry, f"现场照片「{filename}」已留存"

    def attachment_file(self, entry_id: int, stored: str) -> tuple[Path | None, str | None]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, None
        for record in entry.get("attachments", []):
            if record.get("stored") == stored:
                path = UPLOAD_DIR / str(entry_id) / stored
                if path.exists():
                    return path, str(record.get("filename") or stored)
                return None, None
        return None, None

    def export_rows(
        self,
        *,
        keyword: str | None = None,
        station: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[list[Any]], int, str]:
        """按与列表页完全一致的口径取数，保证导出条数与页面统计一致。"""
        rows, total = self.list_entries(keyword=keyword, station=station, source_type=source_type, status=status, page=1, size=100000)
        lines: list[list[Any]] = [EXPORT_HEADER]
        for row in rows:
            lines.append([
                row.get("备案编号", ""),
                row.get("所属站点", ""),
                row.get("干扰源类型", ""),
                row.get("发现时刻", ""),
                row.get("遮挡方位", ""),
                row.get("上报人", ""),
                row.get("核实结论", ""),
                row.get("整改记录", ""),
                row.get("备案状态", ""),
                row.get("重复上报次数", 0),
            ])
        station_label = station.strip() if station and station.strip() else "全部站点"
        filename = f"探测环境备案_{station_label}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        return lines, total, filename

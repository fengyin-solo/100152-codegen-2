"""探测环境变化备案业务规则：撞单去重、状态流转、销号门槛都收在这里。

备案状态推进固定为 待核实 → 已核实 → 已整改 → 已销号；
同一站点同一干扰源在未销号前只保留一条备案，重复上报只回执不落库。
"""
from __future__ import annotations

import threading
from typing import Any

from app.store import store

MODULE = "environment"
REQUIRED_FIELDS = ["所属站点", "干扰源类型", "发现时刻", "遮挡方位"]
STATUS_ORDER = ["待核实", "已核实", "已整改", "已销号"]
CLOSED_STATUS = "已销号"

# 动作 -> (目标状态, 允许的前置状态, 动作必须补充的字段)
ACTION_RULES: dict[str, tuple[str, list[str], str | None]] = {
    "核实": ("已核实", ["待核实"], "核实结论"),
    "整改": ("已整改", ["已核实"], "整改记录"),
    "销号": ("已销号", ["已整改"], None),
}

# 多人同时上报时，编号分配与撞单判断要一起锁住，避免并发落出重复备案。
_create_lock = threading.Lock()


class EnvironmentService:
    def _filter(
        self,
        *,
        keyword: str | None = None,
        station: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("备案编号", ""))]
        if station:
            rows = [row for row in rows if station in str(row.get("所属站点", ""))]
        if source_type:
            rows = [row for row in rows if source_type in str(row.get("干扰源类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

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
        rows = self._filter(keyword=keyword, station=station, source_type=source_type, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(
        self,
        *,
        keyword: str | None = None,
        station: str | None = None,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """页面统计：与列表共用一套过滤口径，保证卡片、合计、导出三方一致。"""
        rows = self._filter(keyword=keyword, station=station, source_type=source_type)
        by_status = {name: 0 for name in STATUS_ORDER}
        for row in rows:
            name = str(row.get("status", ""))
            if name in by_status:
                by_status[name] += 1
        return {"total": len(rows), "byStatus": by_status}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_conflict(self, station: str, source_type: str) -> dict[str, Any] | None:
        """同一站点同一干扰源只留一条在办备案；已销号的归档记录不挡新上报。"""
        for row in store.rows(MODULE):
            if row.get("status") == CLOSED_STATUS:
                continue
            if str(row.get("所属站点", "")) == station and str(row.get("干扰源类型", "")) == source_type:
                return row
        return None

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], dict[str, Any] | None]:
        """登记一条备案。返回 (新备案, 缺失字段, 撞上的在办备案)，后两者至多一个非空。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, None
        station = str(values.get("所属站点") or "").strip()
        source_type = str(values.get("干扰源类型") or "").strip()
        with _create_lock:
            conflict = self._find_conflict(station, source_type)
            if conflict is not None:
                return None, [], conflict
            rows = store.rows(MODULE)
            next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
            entry: dict[str, Any] = {
                "id": next_id,
                "备案编号": f"ENVI-{next_id:04d}",
                "所属站点": station,
                "干扰源类型": source_type,
                "发现时刻": str(values.get("发现时刻") or "").strip(),
                "遮挡方位": str(values.get("遮挡方位") or "").strip(),
                "上报人": str(values.get("上报人") or "").strip(),
                "核实结论": "",
                "整改记录": "",
                "attachments": [],
                "status": STATUS_ORDER[0],
                "pending": True,
                "abnormal": False,
            }
            rows.append(entry)
        return entry, [], None

    def batch_create(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        """多人同时上报：逐条处理、逐条回执，撞单或缺字段不影响其他条。"""
        receipts: list[dict[str, Any]] = []
        for index, values in enumerate(reports, start=1):
            entry, missing, conflict = self.create_entry(values)
            if missing:
                receipts.append({
                    "index": index,
                    "ok": False,
                    "message": f"第 {index} 条缺少必填字段：{'、'.join(missing)}",
                    "entry": None,
                })
            elif conflict is not None:
                receipts.append({
                    "index": index,
                    "ok": False,
                    "message": (
                        f"第 {index} 条与备案 {conflict['备案编号']}（id={conflict['id']}）撞单："
                        "同一站点同一干扰源只保留一条备案"
                    ),
                    "entry": None,
                    "conflictId": conflict["id"],
                    "conflictCode": conflict["备案编号"],
                })
            else:
                receipts.append({
                    "index": index,
                    "ok": True,
                    "message": f"第 {index} 条已登记，备案编号 {entry['备案编号']}",
                    "entry": entry,
                })
        accepted = sum(1 for receipt in receipts if receipt["ok"])
        return {
            "total": len(receipts),
            "accepted": accepted,
            "rejected": len(receipts) - accepted,
            "receipts": receipts,
        }

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"备案 {entry_id} 不存在或已归档"
        if entry.get("status") == CLOSED_STATUS:
            return None, f"备案 {entry.get('备案编号', entry_id)} 已销号，不允许再{action or '操作'}"
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于环境备案可执行范围"
        target, allowed_from, extra_field = rule
        current = str(entry.get("status", ""))
        if current not in allowed_from:
            return None, f"当前状态「{current}」不允许{action}，请按 {' → '.join(STATUS_ORDER)} 推进"
        if extra_field is not None:
            extra = str(values.get(extra_field) or "").strip()
            if not extra:
                return None, f"{action}前必须填写{extra_field}"
            entry[extra_field] = extra
        if action == "销号" and not str(entry.get("核实结论") or "").strip():
            return None, "核实结论缺失，不允许销号"
        entry["status"] = target
        entry["pending"] = target != CLOSED_STATUS
        return entry, f"备案已{action}"

    def add_attachment(
        self, entry_id: int, original_name: str, stored_name: str, size: int
    ) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        attachments = entry.setdefault("attachments", [])
        attachments.append({"name": original_name, "stored": stored_name, "size": size})
        return entry

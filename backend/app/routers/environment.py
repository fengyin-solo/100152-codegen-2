"""探测环境变化备案接口：登记备案、撞单拦截、逐条回执、照片附件与清单导出。

注意路由顺序：/stats、/export、/batch 等固定路径必须写在 /{entry_id} 前面，
否则会被详情路由抢走。
"""
from __future__ import annotations

import csv
import io
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.environment import EnvironmentService

router = APIRouter(prefix="/api/environment", tags=["探测环境变化备案"])

service = EnvironmentService()

# 现场照片落在 backend/uploads/environment/<备案id>/ 下，按时间戳改名避免互相覆盖。
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "environment"

EXPORT_COLUMNS = ["备案编号", "所属站点", "干扰源类型", "发现时刻", "遮挡方位", "核实结论", "整改记录", "备案状态", "现场照片"]


class BatchPayload(BaseModel):
    """多人同时上报时提交的备案集合，每条都会单独给出回执。"""

    reports: list[dict[str, Any]] = Field(default_factory=list)


def _query_filters(
    keyword: str | None,
    station: str | None,
    source_type: str | None,
    status: str | None,
) -> dict[str, str | None]:
    return {"keyword": keyword, "station": station, "source_type": source_type, "status": status}


@router.get("/stats")
def stats(
    keyword: str | None = Query(default=None, description="按备案编号检索"),
    station: str | None = Query(default=None, description="按所属站点检索"),
    source_type: str | None = Query(default=None, description="按干扰源类型检索"),
) -> dict[str, Any]:
    """页面统计：各状态条数与合计，过滤口径和列表、导出完全一致。"""
    return service.stats(keyword=keyword, station=station, source_type=source_type)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按备案编号检索"),
    station: str | None = Query(default=None, description="按所属站点检索"),
    source_type: str | None = Query(default=None, description="按干扰源类型检索"),
    status: str | None = Query(default=None, description="待核实、已核实、已整改、已销号"),
) -> Response:
    """按站点等条件导出备案清单 CSV；导出行数与列表统计共用同一过滤口径。"""
    filters = _query_filters(keyword, station, source_type, status)
    items, total = service.list_entries(**filters, page=1, size=100000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for row in items:
        photos = "、".join(str(item.get("name", "")) for item in row.get("attachments", []))
        writer.writerow([
            _one_line(row.get("备案编号")),
            _one_line(row.get("所属站点")),
            _one_line(row.get("干扰源类型")),
            _one_line(row.get("发现时刻")),
            _one_line(row.get("遮挡方位")),
            _one_line(row.get("核实结论")),
            _one_line(row.get("整改记录")),
            _one_line(row.get("status")),
            _one_line(photos),
        ])
    # utf-8-sig 让 Excel 直接识别中文；一行一条，下载文件的行数可和页面统计对得上。
    content = buffer.getvalue().encode("utf-8-sig")
    filename = quote("探测环境变化备案清单.csv")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=environment-filings.csv; filename*=UTF-8''{filename}",
            "X-Total-Count": str(total),
        },
    )


def _one_line(value: Any) -> str:
    """导出值压成单行，保证一条备案恰好占 CSV 一行。"""
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按备案编号检索"),
    station: str | None = Query(default=None, description="按所属站点检索"),
    source_type: str | None = Query(default=None, description="按干扰源类型检索"),
    status: str | None = Query(default=None, description="待核实、已核实、已整改、已销号"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按备案编号、站点、干扰源类型与状态过滤备案列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = _query_filters(keyword, station, source_type, status)
    items, total = service.list_entries(**filters, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条备案明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"备案 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条环境备案；撞单时不落库，并说明与哪一条撞了。"""
    entry, missing, conflict = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if conflict is not None:
        return ActionResult(
            ok=False,
            message=(
                f"与备案 {conflict['备案编号']}（id={conflict['id']}）撞单："
                "同一站点同一干扰源只保留一条备案，本次上报未重复登记"
            ),
            entry=conflict,
        )
    return ActionResult(ok=True, message=f"环境备案已登记，备案编号 {entry['备案编号']}", entry=entry)


@router.post("/batch")
def batch_create(payload: BatchPayload) -> dict[str, Any]:
    """多人同时上报：逐条处理并逐条给出回执，单条失败不影响其他条。"""
    if not payload.reports:
        raise HTTPException(status_code=400, detail="没有需要上报的备案内容")
    result = service.batch_create(payload.reports)
    return {"ok": result["rejected"] == 0, **result}


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条备案执行核实、整改、销号；不合规的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/attachments")
async def upload_attachment(entry_id: int, file: UploadFile) -> dict[str, Any]:
    """把现场照片作为文件附件留存到对应备案下。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"备案 {entry_id} 不存在或已归档")
    original = Path(file.filename or "photo").name or "photo"
    safe_name = re.sub(r"[^\w.一-鿿-]+", "_", original)
    stored_name = f"{int(time.time() * 1000)}_{safe_name}"
    folder = UPLOAD_ROOT / str(entry_id)
    folder.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    (folder / stored_name).write_bytes(data)
    service.add_attachment(entry_id, original, stored_name, len(data))
    return {"ok": True, "message": f"现场照片 {original} 已留存", "entry": entry}


@router.get("/{entry_id}/attachments/{stored_name}")
def download_attachment(entry_id: int, stored_name: str) -> FileResponse:
    """按备案下载现场照片附件；文件名做了防穿越校验。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"备案 {entry_id} 不存在或已归档")
    if Path(stored_name).name != stored_name:
        raise HTTPException(status_code=400, detail="附件文件名不合法")
    path = UPLOAD_ROOT / str(entry_id) / stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件不存在或已被清理")
    original = next(
        (item["name"] for item in entry.get("attachments", []) if item.get("stored") == stored_name),
        stored_name,
    )
    return FileResponse(path, filename=original)

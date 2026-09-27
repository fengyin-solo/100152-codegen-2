"""探测环境变化备案接口：登记上报、核实整改销号、现场照片附件与按站点导出清单。"""
from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.environment import EnvironmentService

router = APIRouter(prefix="/api/environment", tags=["探测环境备案"])

service = EnvironmentService()

STATUSES = ["待核实", "已核实", "已整改", "已销号"]


class BatchReportPayload(BaseModel):
    """多人同时上报时提交的备案集合；逐条处理并逐条回执。"""

    reports: list[dict[str, Any]] = Field(default_factory=list)


# 注意：/stats、/export 必须声明在 /{entry_id} 之前，否则会被当成备案编号解析成 422。
@router.get("/stats")
def stats() -> dict[str, int]:
    """按状态统计备案量，给页面统计卡片用。"""
    return service.stats()


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按备案编号检索"),
    station: str | None = Query(default=None, description="按站点过滤"),
    source_type: str | None = Query(default=None, description="按干扰源类型过滤"),
    status: str | None = Query(default=None, description="待核实、已核实、已整改、已销号"),
) -> Response:
    """按当前过滤条件导出备案清单 CSV；条数经 X-Total-Count 回传，便于和页面统计核对。"""
    lines, total, filename = service.export_rows(keyword=keyword, station=station, source_type=source_type, status=status)
    buffer = io.StringIO()
    buffer.write("\ufeff")  # 写入 BOM，Excel 直接打开不乱码
    csv.writer(buffer).writerows(lines)
    return Response(
        content=buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"environment.csv\"; filename*=UTF-8''{quote(filename)}",
            "X-Total-Count": str(total),
        },
    )


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按备案编号检索"),
    station: str | None = Query(default=None, description="按站点过滤"),
    source_type: str | None = Query(default=None, description="按干扰源类型过滤"),
    status: str | None = Query(default=None, description="待核实、已核实、已整改、已销号"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按站点、干扰源类型与状态过滤备案列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, station=station, source_type=source_type, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条备案明细（含附件清单）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"备案 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条环境备案；同一站点同一干扰源撞单时不重复登记，并说明撞上了哪一条。"""
    entry, missing, conflict = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if conflict is not None:
        return ActionResult(
            ok=False,
            message=f"与备案 {conflict['备案编号']}（{conflict['所属站点']}·{conflict['干扰源类型']}）撞单，已保留原备案并计入重复上报",
            entry=conflict,
        )
    return ActionResult(ok=True, message=f"备案 {entry['备案编号']} 已登记", entry=entry)


@router.post("/batch")
def batch_create(payload: BatchReportPayload) -> dict[str, Any]:
    """多人同时上报：逐条处理、逐条给回执，撞单或缺字段只影响对应那一行。"""
    if not payload.reports:
        raise HTTPException(status_code=400, detail="批量上报内容为空")
    receipts = service.batch_create(payload.reports)
    accepted = sum(1 for receipt in receipts if receipt["ok"])
    return {"ok": True, "total": len(receipts), "accepted": accepted, "receipts": receipts}


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条备案执行核实、整改、销号；缺核实结论不许销号，已销号不许再核实。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/attachments", response_model=ActionResult)
async def upload_attachment(entry_id: int, file: UploadFile = File(...)) -> ActionResult:
    """上传现场照片：文件落盘留存，备案上登记附件元信息。"""
    content = await file.read()
    entry, message = service.add_attachment(entry_id, file.filename or "现场照片", content)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/{entry_id}/attachments/{stored}")
def download_attachment(entry_id: int, stored: str) -> FileResponse:
    """按备案与附件标识下载现场照片，文件名还原为上传时的原名。"""
    path, display = service.attachment_file(entry_id, stored)
    if path is None:
        raise HTTPException(status_code=404, detail="附件不存在或已删除")
    return FileResponse(path, filename=display)

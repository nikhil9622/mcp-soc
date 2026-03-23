"""Case Management API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.models import (
    Case, CreateCaseRequest, AddNoteRequest, AddTaskRequest,
    UpdateCaseRequest, CaseNote, CaseTask,
)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
async def list_cases(tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    cases = await col.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return cases


@router.post("")
async def create_case(req: CreateCaseRequest, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    case = Case(tenant_id=tenant_id, **req.model_dump())
    await col.insert_one(case.model_dump())
    return case.model_dump()


@router.get("/{case_id}")
async def get_case(case_id: str, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    case = await col.find_one({"tenant_id": tenant_id, "case_id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/{case_id}")
async def update_case(case_id: str, req: UpdateCaseRequest, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.utcnow()
    result = await col.update_one(
        {"tenant_id": tenant_id, "case_id": case_id},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Case not found")
    return await get_case(case_id, tenant_id)


@router.post("/{case_id}/notes")
async def add_note(case_id: str, req: AddNoteRequest, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    note = CaseNote(**req.model_dump())
    result = await col.update_one(
        {"tenant_id": tenant_id, "case_id": case_id},
        {"$push": {"notes": note.model_dump()}, "$set": {"updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Case not found")
    return note.model_dump()


@router.post("/{case_id}/tasks")
async def add_task(case_id: str, req: AddTaskRequest, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    task = CaseTask(title=req.title)
    await col.update_one(
        {"tenant_id": tenant_id, "case_id": case_id},
        {"$push": {"tasks": task.model_dump()}, "$set": {"updated_at": datetime.utcnow()}},
    )
    return task.model_dump()


@router.patch("/{case_id}/tasks/{task_id}")
async def toggle_task(case_id: str, task_id: str, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    case = await col.find_one({"tenant_id": tenant_id, "case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    tasks = case.get("tasks", [])
    for t in tasks:
        if t["task_id"] == task_id:
            t["done"] = not t["done"]
            break
    await col.update_one(
        {"tenant_id": tenant_id, "case_id": case_id},
        {"$set": {"tasks": tasks, "updated_at": datetime.utcnow()}},
    )
    return {"ok": True}


@router.post("/{case_id}/link-incident")
async def link_incident(case_id: str, incident_id: str, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    await col.update_one(
        {"tenant_id": tenant_id, "case_id": case_id},
        {"$addToSet": {"incident_ids": incident_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    return {"ok": True}


@router.delete("/{case_id}")
async def delete_case(case_id: str, tenant_id: str = Depends(get_current_user)):
    col = get_collection("cases")
    await col.delete_one({"tenant_id": tenant_id, "case_id": case_id})
    return {"ok": True}

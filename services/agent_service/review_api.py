#review_api.py

import os, sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.agent_service.tracing import langfuse

from fastapi.middleware.cors import CORSMiddleware
from services.agent_service.graph import app as graph_app
from services.agent_service.notifier import send_failure_email



from contextlib import asynccontextmanager

def setup_retrieval():
    from services.retrieval_service.vectorstore import init_collection, upsert_chunks
    from services.retrieval_service.retriever import build_bm25_index
    from services.chunking_service.parser import parse_document
    from services.chunking_service.chunker import semantic_chunk
    from pathlib import Path

    rules_dir = Path(__file__).resolve().parent.parent.parent / "docs/compliance_rules"
    chunks = []
    for f in sorted(rules_dir.glob("*.md")):
        chunks.extend(semantic_chunk(parse_document(str(f))))
    for i, c in enumerate(chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(chunks)
    build_bm25_index(chunks)
    print(f"✅ 啟動時初始化完成：{len(chunks)} chunks")

@asynccontextmanager
async def lifespan(app):
    setup_retrieval()
    yield











#server = FastAPI(title="IC Spec Guardian API")
server = FastAPI(title="IC Spec Guardian API", lifespan=lifespan)
server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class ReviewRequest(BaseModel):
    spec_content: str
    spec_name: str = "unnamed_spec"
    thread_id: str = "review-1"

class IssueDecision(BaseModel):
    section: str
    action: str          # "confirm" | "reject"
    human_note: Optional[str] = ""

class ApproveRequest(BaseModel):
    decisions: list[IssueDecision]

# ── POST /review/start ────────────────────────────────────────
@server.post("/review/start")
def start_review(req: ReviewRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    initial_state = {
        "spec_content":  req.spec_content,
        "spec_name":     req.spec_name,
        "spec_sections": [],
        "current_index": 0,
        "issues_found":  [],
        "final_report":  "",
    }

    try:
        result = graph_app.invoke(initial_state, config)
    except Exception as e:
        error_msg = str(e)
        send_failure_email(
            thread_id=req.thread_id,
            error=error_msg,
            spec_name=req.spec_name
        )
        raise HTTPException(status_code=500, detail=f"審查失敗：{error_msg}")

    state = graph_app.get_state(config)
    
    if state.next:
        pending = [
            i for i in state.values["issues_found"]
            if i["status"] == "pending_review"
        ]
        langfuse.flush()  #確保 trace 及時送出
        return {
            "status":        "interrupted",
            "thread_id":     req.thread_id,
            "pending_items": pending,
            "message":       f"Stage 1 完成，{len(pending)} 項需人工確認",
        }
    langfuse.flush()  #確保 trace 及時送出
    return {
        "status":       "completed",
        "thread_id":    req.thread_id,
        "final_report": result.get("final_report", ""),
    }

# ── POST /review/approve/{thread_id} ─────────────────────────
@server.post("/review/approve/{thread_id}")
def approve_review(thread_id: str, req: ApproveRequest):
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = graph_app.get_state(config)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"thread_id {thread_id} 不存在")

    current_issues = list(snapshot.values.get("issues_found", []))
    decision_map   = {d.section: d for d in req.decisions}

    updated = []
    for issue in current_issues:
        if issue["status"] == "pending_review":
            decision = decision_map.get(issue["section"])
            if decision:
                new_status = "confirmed" if decision.action == "confirm" else "rejected"
                # if decision.action == "confirm":
                #     new_status = "confirmed"
                # elif decision.action == "skip":
                #     new_status = "skipped"
                # else:
                #     new_status = "rejected"
                updated.append({**issue, "status": new_status, "human_note": decision.human_note})
            else:
                updated.append(issue)
        else:
            updated.append(issue)

    try:
        graph_app.update_state(config, {"issues_found": updated}, as_node="gate")
        result = graph_app.invoke(None, config)
    except Exception as e:
        error_msg = str(e)
        send_failure_email(
            thread_id=thread_id,
            error=f"恢復執行失敗：{error_msg}",
            spec_name=snapshot.values.get("spec_name", "")
        )
        raise HTTPException(status_code=500, detail=f"恢復執行失敗：{error_msg}")

    langfuse.flush()  #確保 trace 及時送出
    return {
        "status":       "completed",
        "thread_id":    thread_id,
        "final_report": result.get("final_report", ""),
    }

# ── GET /review/status/{thread_id} ───────────────────────────
@server.get("/review/status/{thread_id}")
def get_status(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph_app.get_state(config)
    if not snapshot:
        raise HTTPException(status_code=404, detail="not found")

    issues = snapshot.values.get("issues_found", [])
    return {
        "thread_id":  thread_id,
        "next_nodes": list(snapshot.next),
        "pending":    [i for i in issues if i["status"] == "pending_review"],
        "violations": [i for i in issues if i["status"] == "violation"],
        "confirmed":  [i for i in issues if i["status"] == "confirmed"],
        "rejected":   [i for i in issues if i["status"] == "rejected"],
        #"skipped":    [i for i in issues if i["status"] == "skipped"],  # ← 加這行
    }
#test_api.py
import sys, requests, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

BASE_URL = "http://localhost:8002"
THREAD_ID = "api-test-003"

spec_content = Path("docs/test_specs/violation_spec.md").read_text(encoding="utf-8")

# ── Step 1: 開始審查 ─────────────────────────────────────────
print("=" * 50)
print("Step 1: POST /review/start")
print("=" * 50)

r = requests.post(f"{BASE_URL}/review/start", json={
    "spec_content": spec_content,
    "spec_name":    "violation_spec.md",
    "thread_id":    THREAD_ID,
})
result = r.json()
print(json.dumps(result, ensure_ascii=False, indent=2))

if result.get("status") != "interrupted":
    print("⚠️  沒有觸發 HITL，流程結束")
    sys.exit(0)

pending = result.get("pending_items", [])
print(f"\n⏸️  {len(pending)} 項待確認")

# ── Step 2: 查詢狀態 ─────────────────────────────────────────
print("\n" + "=" * 50)
print("Step 2: GET /review/status")
print("=" * 50)

r = requests.get(f"{BASE_URL}/review/status/{THREAD_ID}")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

# ── Step 3: 工程師批准 ───────────────────────────────────────
print("\n" + "=" * 50)
print("Step 3: POST /review/approve")
print("=" * 50)

decisions = [
    {"section": p["section"], "action": "confirm", "human_note": "工程師確認"}
    for p in pending
]
print(f"送出決策：{[d['section'] for d in decisions]}")

r = requests.post(f"{BASE_URL}/review/approve/{THREAD_ID}", json={
    "decisions": decisions
})
final = r.json()
print(json.dumps(final, ensure_ascii=False, indent=2))

# ── Step 4: 測試郵件通知 ─────────────────────────────────────
print("\n" + "=" * 50)
print("Step 4: 測試郵件通知")
print("=" * 50)

from services.agent_service.notifier import send_failure_email
send_failure_email(
    thread_id="api-test-002",
    error="測試：模擬審查流程失敗",
    spec_name="violation_spec.md"
)
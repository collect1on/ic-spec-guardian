# services/agent_service/hitl_runner.py
"""
Human-in-the-Loop 互動執行器
處理：interrupt → 人工輸入 → 恢復執行
"""
USE_MOCK = False  # 預設關閉，測試時從外部改成 True
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from services.agent_service.graph import app


def run_with_hitl(spec_content: str, spec_name: str, thread_id: str = "review-1"):
    """
    執行帶 Human-in-the-Loop 的審查
    遇到低信心違規時暫停，等工程師確認
    """
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "spec_content":          spec_content,
        "spec_name":             spec_name,
        "spec_sections":         [],
        "current_section_index": 0,
        "issues_found":          [],
        "pending_review":        None,
        "human_decision":        None,
        "final_report":          ""
    }

    print(f"\n🚀 開始審查：{spec_name}")
    print("=" * 50)

    # 第一次執行，可能在 human_review 前 interrupt
    result = app.invoke(initial_state, config)

    # 檢查是否被 interrupt
    while True:
        state = app.get_state(config)

        # 看下一個要執行的節點
        next_nodes = state.next

        if not next_nodes:
            # 執行完畢
            break

        if "human_review" in next_nodes:
            # 被 interrupt，需要人工輸入
            pending = state.values.get("pending_review")

            print(f"\n{'='*50}")
            print(f"⏸️  需要人工確認")
            print(f"{'='*50}")
            print(f"章節：{pending['section']}")
            print(f"規則：{pending['rule_id']}")
            print(f"描述：{pending['description']}")
            print(f"信心：{pending['confidence']:.2f}")
            print(f"\n請輸入決定：")
            print(f"  [c] confirm  → 確認這是違規")
            print(f"  [r] reject   → 否決，不是違規")
            print(f"  [s] skip     → 跳過，標記待審")

            choice = input("\n你的選擇 (c/r/s)：").strip().lower()
            decision_map = {"c": "confirm", "r": "reject", "s": "skip"}
            decision = decision_map.get(choice, "skip")

            # 把人工決定寫回 state，恢復執行
            app.update_state(
                config,
                {"human_decision": decision},
                #as_node="human_review"
            )

            # 繼續執行
            result = app.invoke(None, config)

        else:
            break

    # 取得最終結果
    final_state = app.get_state(config)
    return final_state.values

if __name__ == "__main__":
    from services.retrieval_service.vectorstore import init_collection, upsert_chunks
    from services.retrieval_service.retriever import build_bm25_index
    from services.chunking_service.parser import parse_document
    from services.chunking_service.chunker import semantic_chunk

    # ── 開啟 Mock 模式（放在最前面）──
    import services.agent_service.graph as graph_module
    graph_module.USE_MOCK = True
    from services.agent_service.graph import build_graph, MemorySaver
    _memory = MemorySaver()
    _app    = build_graph(checkpointer=_memory)

    # hitl_runner 裡的 app 也要換成 mock 版
    import services.agent_service.hitl_runner as hitl_module
    hitl_module.app = _app

    # 初始化檢索
    rules_dir = repo_root / "docs/compliance_rules"
    all_chunks = []
    for md_file in sorted(rules_dir.glob("*.md")):
        chunks = semantic_chunk(parse_document(str(md_file)))
        all_chunks.extend(chunks)
    for i, c in enumerate(all_chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(all_chunks)
    build_bm25_index(all_chunks)
    print(f"✅ {len(all_chunks)} 個規範 chunks 就緒")

    # 讀取 violation spec
    spec_path = repo_root / "docs/test_specs/violation_spec.md"
    with open(spec_path, encoding="utf-8") as f:
        spec_content = f.read()

    # 執行
    result = run_with_hitl(spec_content, "violation_spec.md", thread_id="test-hitl-1")

    print("\n" + "=" * 50)
    print("📊 最終報告")
    print("=" * 50)
    print(result.get("final_report", "無報告"))
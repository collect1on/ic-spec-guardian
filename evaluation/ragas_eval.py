# evaluation/ragas_eval.py
"""
RAGAS 評測框架（20題完整版）
- RAG 答案生成：Gemini 2.5 Flash
- RAGAS 指標計算：Gemini 2.5 Flash
- Embedding：本地 Ollama nomic-embed-text
"""
import warnings
warnings.filterwarnings('ignore')

import sys, json, os, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from datasets import Dataset
from ragas import evaluate, RunConfig
from ragas.metrics import (
    _LLMContextPrecisionWithReference as ContextPrecision,
    _LLMContextRecall as ContextRecall,
    _Faithfulness as Faithfulness,
    _ResponseRelevancy as AnswerRelevancy,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index, hybrid_search
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk

# ── 模型設定 ────────────────────────────────────────────────
def get_rag_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

def get_ragas_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

def get_ragas_embeddings():
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )

# ── Step 1：確保向量庫與 BM25 就緒 ─────────────────────────
def setup_retrieval():
    print("📂 載入規範文件至 Qdrant & BM25...")
    rules_dir = repo_root / "docs/compliance_rules"
    all_chunks = []
    for md_file in sorted(rules_dir.glob("*.md")):
        raw = parse_document(str(md_file))
        chunks = semantic_chunk(raw)
        all_chunks.extend(chunks)
        print(f"   ✅ {md_file.name}：{len(chunks)} chunks")
    for i, c in enumerate(all_chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(all_chunks)
    build_bm25_index(all_chunks)
    print(f"📊 總計 {len(all_chunks)} 個 chunks 就緒\n")
    return all_chunks

# ── Step 2：單一問題 RAG 流程 ──────────────────────────────
def run_rag(question: str, llm) -> tuple[str, list[str]]:
    try:
        retrieved = hybrid_search(question, top_k=3)
        contexts = [r["text"] for r in retrieved]
    except Exception:
        contexts = []

    if not contexts:
        return "無法檢索到相關規範內容", []

    context_str = "\n\n---\n\n".join(contexts)
#     prompt = f"""你是 IC 設計合規審查專家。
# 請嚴格根據以下規範內容回答問題。若內容未提及，請回答「無法確認」。

# 規範內容：
# {context_str}

# 問題：{question}
#   llm_context_precision_with_reference     0.875  █████████████████
#   context_recall                           1.000  ████████████████████
#   faithfulness                             0.954  ███████████████████
#   answer_relevancy                         0.691  █████████████





# 請用繁體中文簡潔回答，並引用相關規則 ID（如有）："""
#     prompt = f"""你是 IC 設計合規審查專家。
# 根據以下規範內容，用一到兩句話直接回答問題。只回答問題本身，不要加額外說明。請完整回答問題中的後果、影響與原因。

# 規範內容：
# {context_str}

# 問題：{question}
# 答案："""
#   llm_context_precision_with_reference     0.875  █████████████████
#   context_recall                           1.000  ████████████████████
#   faithfulness                             0.800  ████████████████
#   answer_relevancy                         0.666  █████████████






    prompt = f"""你是 IC 設計合規審查專家。
請嚴格根據以下規範內容回答問題。請完整回答問題中的後果、影響與原因，並引用相關規則 ID（如有）。若內容未提及，請回答「無法確認」。

規範內容：
{context_str}

問題：{question}

："""

# """  llm_context_precision_with_reference     0.867  █████████████████
#   context_recall                           1.000  ████████████████████
#   faithfulness                             0.913  ██████████████████
#   answer_relevancy                         0.806  ████████████████"""

    try:
        response = llm.invoke(prompt)
        return (getattr(response, "content", None) or str(response)).strip(), contexts
    except Exception as e:
        print(f"   ⚠️ LLM 錯誤：{e}")
        return "LLM 處理時發生錯誤", contexts

# ── Step 3：建構 Dataset ───────────────────────────────────
def build_dataset(qa_pairs: list[dict], llm) -> Dataset:
    print(f"🤖 對 {len(qa_pairs)} 題 QA 執行 RAG 生成答案...")
    rows = []
    for i, qa in enumerate(qa_pairs):
        print(f"   [{i+1}/{len(qa_pairs)}] {qa['question'][:50]}...")
        answer, contexts = run_rag(qa["question"], llm)
        rows.append({
            "question":     qa["question"],
            "answer":       answer,
            "contexts":     contexts,
            "ground_truth": qa["ground_truth"],
        })
        time.sleep(0.5)  # 避免 API rate limit
    return Dataset.from_list(rows)

# ── Step 4：執行 RAGAS 評測 ────────────────────────────────
def run_evaluation(dataset: Dataset, llm, embeddings):
    print("\n📊 計算 RAGAS 四項指標...")
    result = evaluate(
        dataset=dataset,
        metrics=[
            ContextPrecision(),
            ContextRecall(),
            Faithfulness(),
            AnswerRelevancy(),
        ],
        llm=LangchainLLMWrapper(llm),
        embeddings=LangchainEmbeddingsWrapper(embeddings),
        run_config=RunConfig(max_workers=1, timeout=180),
        raise_exceptions=False
    )
    return result

# ── Step 5：儲存報告 ───────────────────────────────────────
def save_report(result, version: str = "v1"):
    report_dir = repo_root / "evaluation/reports"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    df = result.to_pandas()

    # ── 1. 存完整明細（含 LLM 回答文本）──
    detail_path = report_dir / f"ragas_{version}_{timestamp}_detail.json"
    detail_records = []
    for _, row in df.iterrows():
        record = {
            "question":   row.get("user_input", ""),
            "answer":     row.get("response", ""),
            "contexts":   row.get("retrieved_contexts", []),
            "reference":  row.get("reference", ""),
            "scores": {
                "context_precision": round(float(row.get("llm_context_precision_with_reference", 0)), 4),
                "context_recall":    round(float(row.get("context_recall", 0)), 4),
                "faithfulness":      round(float(row.get("faithfulness", 0)), 4),
                "answer_relevancy":  round(float(row.get("answer_relevancy", 0)), 4),
            }
        }
        detail_records.append(record)

    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail_records, f, ensure_ascii=False, indent=2)
    print(f"📋 明細已儲存：{detail_path}")

    # ── 2. 存摘要分數 ──
    metric_cols = [
        "llm_context_precision_with_reference",
        "context_recall",
        "faithfulness",
        "answer_relevancy"
    ]
    scores = {}
    for col in metric_cols:
        if col in df.columns:
            scores[col] = round(float(df[col].mean()), 4)

    summary_path = report_dir / f"ragas_{version}_{timestamp}.json"
    report = {
        "version":          version,
        "timestamp":        timestamp,
        "total_questions":  len(df),
        "scores":           scores,
        "threshold": {
            "context_recall": 0.75,
            "passed":         scores.get("context_recall", 0) >= 0.75
        }
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"💾 摘要已儲存：{summary_path}")

    return scores

# ── Step 6：門檻檢查（CI/CD 用）────────────────────────────
def check_threshold(scores: dict):
    recall = scores.get("context_recall", 0)
    if recall < 0.75:
        print(f"\n❌ context_recall {recall:.3f} 低於門檻 0.75")
        if os.getenv("CI") == "true":
            sys.exit(1)
    else:
        print(f"\n✅ context_recall {recall:.3f} 通過門檻 0.75")

# ── 主流程 ─────────────────────────────────────────────────
def main(version: str = "v1"):
    print("=" * 55)
    print("🧪 IC Spec Guardian - RAGAS 完整評測")
    print("=" * 55 + "\n")

    setup_retrieval()
    rag_llm      = get_rag_llm()
    ragas_llm    = get_ragas_llm()
    ragas_emb    = get_ragas_embeddings()

    with open(repo_root / "evaluation/ground_truth_qa.json", encoding="utf-8") as f:
        qa_pairs = json.load(f)
    print(f"📋 載入 {len(qa_pairs)} 題 Ground Truth QA\n")

    # 生成答案
    dataset = build_dataset(qa_pairs, rag_llm)

    # 計算指標
    result = run_evaluation(dataset, ragas_llm, ragas_emb)

    # 顯示結果
    print("\n" + "=" * 40)
    print("📊 評測結果")
    print("=" * 40)
    df = result.to_pandas()

    metric_cols = [
        "llm_context_precision_with_reference",
        "context_recall",
        "faithfulness",
        "answer_relevancy"
    ]
    for col in metric_cols:
        if col in df.columns:
            val = float(df[col].mean())
            bar = "█" * int(val * 20)
            print(f"  {col:<40} {val:.3f}  {bar}")

    # 存報告
    #scores = save_report(df, version)
    scores = save_report(result, version)
    # 門檻檢查
    check_threshold(scores)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1", help="報告版本標籤")
    args = parser.parse_args()
    main(args.version)
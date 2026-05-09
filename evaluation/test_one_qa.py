# evaluation/test_one_qa.py
"""
單題 QA 測試：驗證 RAGAS 評測管線是否正常運作
確認無誤後再跑完整 20 題
"""
import warnings
warnings.filterwarnings('ignore')

import sys, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings
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
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index, hybrid_search
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk

# ── 單題測試資料 ────────────────────────────────────────────
TEST_QA = {
    "question": "AXI4 Master 介面必須支援哪些 burst 模式？",
    "ground_truth": "必須同時支援 INCR 和 WRAP 兩種 burst 模式，依據規則 AXI-001。"
}

def setup_retrieval():
    print("📂 載入規範文件...")
    rules_dir = repo_root / "docs/compliance_rules"
    all_chunks = []
    for md_file in sorted(rules_dir.glob("*.md")):
        raw = parse_document(str(md_file))
        chunks = semantic_chunk(raw)
        all_chunks.extend(chunks)
    for i, c in enumerate(all_chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(all_chunks)
    build_bm25_index(all_chunks)
    print(f"✅ {len(all_chunks)} 個 chunks 就緒\n")

def run_rag(question: str, llm) -> tuple[str, list[str]]:
    retrieved = hybrid_search(question, top_k=3)
    contexts = [r["text"] for r in retrieved]
    context_str = "\n\n---\n\n".join(contexts)
    prompt = f"""你是 IC 設計合規審查專家。
請嚴格根據以下規範內容回答問題。若內容未提及，請回答「無法確認」。

規範內容：
{context_str}

問題：{question}

請用繁體中文簡潔回答，並引用相關規則 ID（如有）："""
    response = llm.invoke(prompt)
    answer = (getattr(response, "content", None) or str(response)).strip()
    return answer, contexts

def main():
    print("=" * 50)
    print("🧪 單題 QA 管線測試")
    print("=" * 50)

    # Step 1：初始化檢索
    setup_retrieval()

    # Step 2：初始化模型
    # rag_llm = ChatOllama(
    #     model="gemma4:e4b",
    #     base_url="http://localhost:11434",
    #     temperature=0,
    #     num_predict=512,
    # )
    rag_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
    )
    
    ragas_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )
    ragas_emb = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )
    # Step 3：跑 RAG
    print(f"🔎 問題：{TEST_QA['question']}")
    answer, contexts = run_rag(TEST_QA["question"], rag_llm)
    print(f"\n💬 RAG 答案：{answer}")
    print(f"\n📄 檢索到 {len(contexts)} 個 contexts")
    for i, ctx in enumerate(contexts, 1):
        print(f"   [{i}] {ctx[:80]}...")

    # Step 4：建立單題 Dataset
    dataset = Dataset.from_list([{
        "question":     TEST_QA["question"],
        "answer":       answer,
        "contexts":     contexts,
        "ground_truth": TEST_QA["ground_truth"],
    }])

    # Step 5：RAGAS 評測
    print("\n📊 計算 RAGAS 指標...")
    result = evaluate(
        dataset=dataset,
        metrics=[
            ContextPrecision(),
            ContextRecall(),
            Faithfulness(),
            AnswerRelevancy(),
        ],
        llm=LangchainLLMWrapper(ragas_llm),
        embeddings=LangchainEmbeddingsWrapper(ragas_emb),
        run_config=RunConfig(max_workers=1, timeout=180),
        raise_exceptions=False
    )

    #scores = result.scores if hasattr(result, 'scores') else dict(result)

    # Step 6：顯示結果
    # print("\n" + "=" * 40)
    # print("📊 單題評測結果")
    # print("=" * 40)
    # for m in ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]:
    #     val = float(scores.get(m, 0))
    #     bar = "█" * int(val * 20)
    #     print(f"  {m:<22} {val:.3f}  {bar}")

    # print("\n✅ 單題測試完成，管線正常！" if any(
    #     float(scores.get(m, 0)) > 0
    #     for m in scores
    # ) else "\n⚠️  分數全為 0，請檢查模型輸出")

    print("\n" + "=" * 40)
    print("📊 單題評測結果")
    print("=" * 40)

    # RAGAS 0.4 回傳 EvaluationResult，先轉成 DataFrame
    df = result.to_pandas()
    print(df.to_string())

    # 同時印出每個指標的平均值
    print("\n--- 指標平均值 ---")
    metrics = ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]
    for m in metrics:
        if m in df.columns:
            val = float(df[m].mean())
            bar = "█" * int(val * 20)
            print(f"  {m:<22} {val:.3f}  {bar}")

    print("\n✅ 單題測試完成，管線正常！")
    
    
if __name__ == "__main__":
    main()
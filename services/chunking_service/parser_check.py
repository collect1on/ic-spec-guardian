"""
Document Parser: 支援 Markdown 與 PDF 解析
輸出格式：list[dict]，每個 chunk 包含 text + metadata
"""
import re
import hashlib
import json
from pathlib import Path

def generate_id(text: str, source: str, index: int) -> str:
    """產生唯一 chunk ID"""
    content = f"{source}:{text[:50].strip()}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def parse_markdown(path: str, verbose: bool = False) -> list[dict]:
    """解析 Markdown 文件，依 ## 標題切分章節"""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if verbose:
        print("\n" + "="*80)
        print("📄 PARSER 開始解析 Markdown")
        print("="*80)
        print(f"📁 檔案: {path}")
        print(f"📏 原始檔案大小: {len(content)} 字元")
        print(f"📊 原始內容前 200 字:\n{content[:200]}...\n")
    
    # 使用多行模式切分 ## 開頭的區塊（更穩健）
    parts = re.split(r'(?m)^##\s+', content)
    
    if verbose:
        print(f"✂️  正則表達式切分: r'(?m)^##\\s+'")
        print(f"📦 切分後得到 {len(parts)} 個部分\n")
    
    chunks = []
    for i, part in enumerate(parts):
        if verbose:
            print(f"{'─'*80}")
            print(f"🔍 處理第 {i} 個部分:")
            print(f"   原始內容前 100 字: {part[:100]}...")
        
        part = part.strip()
        if not part:
            if verbose:
                print("   ⏭️  空內容，跳過")
            continue
            
        # 第一行是標題，其餘是內文
        lines = part.split('\n', 1)
        heading_text = lines[0].strip()
        body_text = lines[1].strip() if len(lines) > 1 else ""
        
        if verbose:
            print(f"   📌 標題: {heading_text}")
            print(f"   📝 內文長度: {len(body_text)} 字元")
            print(f"   📝 內文前 50 字: {body_text[:50]}...")
        
        heading = f"## {heading_text}"
        
        # 提取 Rule ID (如 AXI-001)
        rule_match = re.search(r'([A-Z]{2,4}-\d{3})', heading_text)
        rule_id = rule_match.group(1) if rule_match else None
        
        if verbose:
            print(f"   🔎 尋找 Rule ID (pattern: [A-Z]{{2,4}}-\\d{{3}})")
            print(f"   {'✅ 找到' if rule_id else '❌ 未找到'} Rule ID: {rule_id}")
        
        full_text = f"{heading}\n\n{body_text}"
        
        chunk = {
            "text": full_text,
            "heading": heading_text,
            "source": Path(path).name,
            "rule_id": rule_id,
            "chunk_id": generate_id(full_text, path, i)
        }
        
        if verbose:
            print(f"   🏷️  生成 chunk_id: {chunk['chunk_id']}")
            print(f"   📦 Chunk 完整結構:")
            # 只顯示 text 前 100 字，避免太長
            display_chunk = {**chunk, "text": chunk["text"][:100] + "..."}
            print(f"   {json.dumps(display_chunk, ensure_ascii=False, indent=6)}")
        
        chunks.append(chunk)
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"✅ PARSER 完成，共產生 {len(chunks)} 個 chunks")
        print(f"{'='*80}\n")
        
        # 總覽表
        print("📊 PARSER 輸出總覽:")
        print(f"{'ID':<15} {'Heading':<30} {'Rule ID':<12} {'Text Length':<12} {'Source'}")
        print("-"*80)
        for c in chunks:
            print(f"{c['chunk_id']:<15} {c['heading'][:28]:<30} {str(c['rule_id']):<12} {len(c['text']):<12} {c['source']}")
    
    return chunks

def parse_pdf(path: str, verbose: bool = False) -> list[dict]:
    """PDF 解析（備援方案）"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("請安裝: pip install pymupdf")
    
    if verbose:
        print("\n" + "="*80)
        print("📄 PARSER 開始解析 PDF")
        print("="*80)
        print(f"📁 檔案: {path}")
    
    doc = fitz.open(path)
    
    if verbose:
        print(f"📑 PDF 總頁數: {len(doc)}")
    
    chunks = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        
        if verbose:
            print(f"{'─'*80}")
            print(f"📄 第 {page_num + 1} 頁:")
            print(f"   文字長度: {len(text)} 字元")
            print(f"   前 100 字: {text[:100]}...")
        
        if text.strip():
            chunk = {
                "text": text,
                "heading": f"Page {page_num + 1}",
                "source": Path(path).name,
                "page": page_num + 1,
                "rule_id": None,
                "chunk_id": generate_id(text, path, page_num)
            }
            
            if verbose:
                print(f"   🏷️  chunk_id: {chunk['chunk_id']}")
            
            chunks.append(chunk)
        else:
            if verbose:
                print("   ⏭️  空白頁，跳過")
    
    doc.close()
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"✅ PDF PARSER 完成，共 {len(chunks)} 頁有內容")
        print(f"{'='*80}\n")
    
    return chunks

def parse_document(path: str, verbose: bool = False) -> list[dict]:
    """統一入口：依副檔名選擇解析器"""
    path = Path(path)
    
    if verbose:
        print("\n" + "🚀"*40)
        print(f"📂 開始解析文件: {path.name}")
        print(f"📎 副檔名: {path.suffix}")
    
    if path.suffix == '.md':
        result = parse_markdown(str(path), verbose=verbose)
    elif path.suffix == '.pdf':
        result = parse_pdf(str(path), verbose=verbose)
    else:
        raise ValueError(f"不支援的格式: {path.suffix}")
    
    if verbose:
        print("\n" + "🎯"*40)
        print(f"📊 最終輸出: {len(result)} 個結構化 chunks")
        print(f"📋 總字數統計: {sum(len(c['text']) for c in result)} 字元")
        print(f"🔢 Rule IDs: {[c.get('rule_id') for c in result if c.get('rule_id')]}")
        print("🎯"*40 + "\n")
    
    return result

# 測試代碼
if __name__ == "__main__":
    # 找一個測試文件
    test_file = None
    
    # 嘗試找 markdown 文件
    docs_dir = Path(__file__).parent.parent.parent / "docs"
    if docs_dir.exists():
        md_files = list(docs_dir.rglob("*.md"))
        if md_files:
            test_file = str(md_files[0])
            print(f"🔍 找到測試文件: {test_file}")
    
    if test_file:
        # 執行解析並顯示所有中間資料
        chunks = parse_document(test_file, verbose=True)
        
        # 顯示最終的 Python 資料結構
        print("\n" + "="*80)
        print("🐍 最終 Python 資料結構（第一個 chunk）:")
        print("="*80)
        if chunks:
            import pprint
            # 截斷 text 以便顯示
            display = chunks[0].copy()
            if len(display['text']) > 200:
                display['text'] = display['text'][:200] + "... [截斷]"
            pprint.pprint(display, indent=2, width=80)
    else:
        print("❌ 找不到測試文件")
        print("請將 Markdown 文件放在 docs/ 目錄下，或直接指定路徑:")
        print("示例: parse_document('path/to/your/file.md', verbose=True)")
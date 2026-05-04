"""
Document Parser: 支援 Markdown 與 PDF 解析
輸出格式：list[dict]，每個 chunk 包含 text + metadata
"""
import re
import hashlib
from pathlib import Path

def generate_id(text: str, source: str, index: int) -> str:
    """產生唯一 chunk ID"""
    content = f"{source}:{text[:50].strip()}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def parse_markdown(path: str) -> list[dict]:
    """解析 Markdown 文件，依 ## 標題切分章節"""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用多行模式切分 ## 開頭的區塊（更穩健）
    parts = re.split(r'(?m)^##\s+', content)
    
    chunks = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
            
        # 第一行是標題，其餘是內文
        lines = part.split('\n', 1)
        heading_text = lines[0].strip()
        body_text = lines[1].strip() if len(lines) > 1 else ""
        
        heading = f"## {heading_text}"
        
        # 提取 Rule ID (如 AXI-001)
        rule_match = re.search(r'([A-Z]{2,4}-\d{3})', heading_text)
        rule_id = rule_match.group(1) if rule_match else None
        
        full_text = f"{heading}\n\n{body_text}"
        
        chunks.append({
            "text": full_text,
            "heading": heading_text,
            "source": Path(path).name,
            "rule_id": rule_id,
            "chunk_id": generate_id(full_text, path, i)
        })
        
    return chunks

def parse_pdf(path: str) -> list[dict]:
    """PDF 解析（備援方案）"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("請安裝: pip install pymupdf")
        
    doc = fitz.open(path)
    chunks = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            chunks.append({
                "text": text,
                "heading": f"Page {page_num + 1}",
                "source": Path(path).name,
                "page": page_num + 1,
                "rule_id": None,
                "chunk_id": generate_id(text, path, page_num)
            })
    doc.close()
    return chunks

def parse_document(path: str) -> list[dict]:
    """統一入口：依副檔名選擇解析器"""
    path = Path(path)
    if path.suffix == '.md':
        return parse_markdown(str(path))
    elif path.suffix == '.pdf':
        return parse_pdf(str(path))
    else:
        raise ValueError(f"不支援的格式: {path.suffix}")

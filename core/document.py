# -*- coding: utf-8 -*-
"""
Ezy-RAG — 文档处理模块
提供文件读取和文档加载功能
"""
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger("Ezy-RAG-Doc")


# ============================================================
#  文件读取
# ============================================================

def read_pdf(filepath: str) -> str:
    """读取 PDF 文件"""
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            texts.append(t)
    return "\n".join(texts)


def read_docx(filepath: str) -> str:
    """读取 DOCX 文件"""
    from docx import Document as DocxDocument
    doc = DocxDocument(filepath)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_txt(filepath: str) -> str:
    """读取纯文本文件（自动检测编码）"""
    for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def read_md(filepath: str) -> str:
    """读取 Markdown 文件"""
    return read_txt(filepath)


# 支持的文件扩展名映射
SUPPORTED_EXT = {
    ".pdf": read_pdf, ".docx": read_docx, ".txt": read_txt, ".md": read_md,
    ".py": read_txt, ".js": read_txt, ".ts": read_txt, ".java": read_txt,
    ".c": read_txt, ".cpp": read_txt, ".go": read_txt, ".rs": read_txt,
    ".r": read_txt, ".R": read_txt, ".sh": read_txt, ".ps1": read_txt,
    ".swift": read_txt, ".kt": read_txt, ".rb": read_txt, ".lua": read_txt,
    ".sql": read_txt, ".json": read_txt, ".yaml": read_txt, ".yml": read_txt,
    ".csv": read_txt, ".xml": read_txt, ".toml": read_txt, ".ini": read_txt,
    ".cfg": read_txt, ".conf": read_txt, ".log": read_txt, ".html": read_txt,
    ".css": read_txt,
}


def read_file(filepath: str) -> str:
    """统一文件读取，根据扩展名选择读取方式"""
    ext = Path(filepath).suffix.lower()
    reader_fn = SUPPORTED_EXT.get(ext)
    if not reader_fn:
        raise ValueError(f"不支持的文件格式: {ext}")
    return reader_fn(filepath)


def load_all_documents(*dirs: Path) -> List[dict]:
    """加载多个目录下的所有文档
    
    Args:
        *dirs: 一个或多个目录路径
        
    Returns:
        文档列表，每个文档包含 path 和 text 字段
    """
    documents = []
    seen = set()
    for docs_dir in dirs:
        if not docs_dir.exists():
            continue
        for ext, reader_fn in SUPPORTED_EXT.items():
            for f in docs_dir.glob(f"**/*{ext}"):
                if not f.is_file():
                    continue
                key = str(f.resolve())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    text = reader_fn(str(f))
                    if text.strip():
                        doc_name = f.stem
                        text = f"[文件名: {doc_name}]\n{text}"
                        documents.append({"path": str(f), "text": text})
                        logger.info(f"加载: {f.name} ({len(text)} 字)")
                    else:
                        logger.debug(f"跳过: {f.name} (无文字内容)")
                except Exception as e:
                    logger.warning(f"加载失败: {f.name}: {e}")
    logger.info(f"共加载 {len(documents)} 份文档")
    return documents

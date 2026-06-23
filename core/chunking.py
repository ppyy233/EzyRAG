# -*- coding: utf-8 -*-
"""
Ezy-RAG — 文本切分模块
提供多种文本切分策略

策略列表：
- recursive: 递归分层切片（段落 → 句子 → 字符）
- flat: 扁平切片
- sentence: 句子级切片（按句子边界切分）
- markdown_header: Markdown 标题切片（按标题层级切分）
"""
import re
from datetime import datetime
from pathlib import Path
from typing import List

from core.utils import content_hash, md5_short


def split_text(text: str, cfg: dict) -> List[str]:
    """按模板配置切片"""
    chunk_size = cfg["chunk_size"]
    overlap = cfg["overlap"]
    strategy = cfg.get("strategy", "flat")
    separators = cfg.get("separators", [])
    
    if strategy == "recursive":
        return _split_recursive(text, chunk_size, overlap, separators)
    elif strategy == "sentence":
        overlap_sentences = cfg.get("overlap_sentences", 2)
        return _split_sentence(text, chunk_size, overlap_sentences)
    elif strategy == "markdown_header":
        return _split_markdown_headers(text, chunk_size)
    else:
        return _split_flat(text, chunk_size, overlap, separators)


def _split_recursive(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """递归分层切片：段落 → 句子 → 字符"""
    para_seps = [s for s in separators if s in ("\n\n", "\r\n\r\n", "\r\n")]
    if not para_seps:
        para_seps = ["\n\n"]

    paragraphs = [text]
    for s in para_seps:
        expanded = []
        for p in paragraphs:
            expanded.extend(p.split(s))
        paragraphs = expanded
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    sent_seps = [s for s in separators
                 if s not in ("\n\n", "\r\n\r\n", "\r\n", " ", "") and s]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) <= chunk_size:
            if current:
                _add_segment(current, para, chunk_size, overlap, chunks)
            current = _update_current(current, para, chunk_size, overlap)
            if para == paragraphs[-1]:
                continue
            continue

        sentences = [para]
        for raw_s in sent_seps:
            s = "\n" if raw_s == "\n" else raw_s
            if s == "\n" and "\n\n" in separators:
                continue
            expanded = []
            for seg in sentences:
                expanded.extend(seg.split(s))
            sentences = expanded
        sentences = [seg.strip() + _pick_suffix(para, seg) for seg in sentences if seg.strip()]
        sentences = [seg.rstrip() for seg in sentences if seg.strip()]

        for sent in sentences:
            if len(sent) > chunk_size:
                _hard_split_long(sent, chunk_size, overlap, chunks)
                current = ""
                continue
            _add_segment(current, sent, chunk_size, overlap, chunks)
            current = _update_current(current, sent, chunk_size, overlap)

    if current.strip():
        chunks.append(current.strip())
    return _final_pass(chunks, chunk_size)


def _split_flat(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """扁平切片"""
    parts = [text]
    for s in separators:
        if not s:
            continue
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(s))
        parts = new_parts
    segments = [seg.strip() for seg in parts if seg.strip()]

    chunks = []
    current = ""
    for seg in segments:
        if current and len(current) + len(seg) > chunk_size:
            chunks.append(current.strip())
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + " " + seg
            else:
                current = seg
        else:
            current = current + " " + seg if current else seg
    if current.strip():
        chunks.append(current.strip())
    return _final_pass(chunks, chunk_size)


def _split_sentence(text: str, chunk_size: int, overlap_sentences: int = 2) -> List[str]:
    """句子级切片：按句子边界切分，支持中英文
    
    特点：
    - 保持句子完整性
    - 按句子数量设置重叠（而非字符数）
    - 适合 FAQ、短文档、知识库条目
    """
    # 保护缩写和小数点中的句号
    protected = text
    protected = re.sub(r'(?<=\w)\.(?=\w)', '§DOT§', protected)  # U.S.A.
    protected = re.sub(r'(\d)\.(\d)', r'\1§DOT§\2', protected)   # 3.14
    
    # 按句子结束符切分（支持中英文）
    sentences = re.split(r'(?<=[。！？；.!?;\n])\s*', protected)
    sentences = [s.replace('§DOT§', '.').strip() for s in sentences if s.strip()]
    
    if not sentences:
        return [text] if text.strip() else []
    
    # 按 chunk_size 分组句子
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sent in sentences:
        if current_len + len(sent) > chunk_size and current_chunk:
            chunks.append("".join(current_chunk))
            # 重叠：保留最后 N 个句子
            if overlap_sentences > 0:
                current_chunk = current_chunk[-overlap_sentences:]
                current_len = sum(len(s) for s in current_chunk)
            else:
                current_chunk = []
                current_len = 0
        
        current_chunk.append(sent)
        current_len += len(sent)
    
    if current_chunk:
        chunks.append("".join(current_chunk))
    
    return [c.strip() for c in chunks if c.strip()]


def _split_markdown_headers(text: str, chunk_size: int) -> List[str]:
    """Markdown 标题切片：按标题层级切分
    
    特点：
    - 按 # ## ### 等标题切分
    - 保留标题作为 chunk 开头
    - 适合 Markdown 文档、Wiki、README
    """
    lines = text.split("\n")
    chunks = []
    current_content = []
    current_header = ""  # 当前标题层级文本
    
    for line in lines:
        stripped = line.strip()
        
        # 检测 Markdown 标题
        header_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        
        if header_match:
            # 遇到新标题，先保存之前的内容
            if current_content:
                chunk_text = "\n".join(current_content).strip()
                if chunk_text:
                    # 如果有标题前缀，加到开头
                    if current_header:
                        chunk_text = current_header + "\n" + chunk_text
                    chunks.append(chunk_text)
                current_content = []
            
            # 更新当前标题
            current_header = stripped
        elif stripped:
            current_content.append(stripped)
        
        # 如果当前内容超过 chunk_size，强制切分
        content_len = sum(len(c) for c in current_content)
        if content_len > chunk_size:
            # 尝试在空行处切分
            content_text = "\n".join(current_content)
            last_break = content_text.rfind("\n\n", 0, chunk_size)
            
            if last_break > 0:
                chunk_part = content_text[:last_break].strip()
                if current_header:
                    chunk_part = current_header + "\n" + chunk_part
                chunks.append(chunk_part)
                current_content = [content_text[last_break:].strip()]
            else:
                # 没有空行，硬切
                chunk_part = content_text[:chunk_size].strip()
                if current_header:
                    chunk_part = current_header + "\n" + chunk_part
                chunks.append(chunk_part)
                current_content = [content_text[chunk_size:].strip()]
    
    # 保存剩余内容
    if current_content:
        chunk_text = "\n".join(current_content).strip()
        if chunk_text:
            if current_header:
                chunk_text = current_header + "\n" + chunk_text
            chunks.append(chunk_text)
    
    return [c for c in chunks if c.strip()]


def _add_segment(current: str, seg: str, chunk_size: int, overlap: int, chunks: list):
    if not current:
        return
    if len(current) + len(seg) > chunk_size:
        chunks.append(current.strip())


def _update_current(current: str, seg: str, chunk_size: int, overlap: int) -> str:
    if not current:
        return seg
    if len(current) + len(seg) > chunk_size:
        if overlap > 0 and len(current) > overlap:
            return current[-overlap:] + " " + seg
        return seg
    return current + " " + seg


def _pick_suffix(text: str, seg: str) -> str:
    idx = text.find(seg)
    if idx < 0:
        return ""
    end = idx + len(seg)
    if end < len(text) and text[end] in ".。!！?？;；":
        return text[end]
    return ""


def _hard_split_long(text: str, chunk_size: int, overlap: int, chunks: list):
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        if end >= len(text):
            chunks.append(text[i:].strip())
            break
        cut = text.rfind(" ", i, end)
        if cut > i + chunk_size // 2:
            chunks.append(text[i:cut].strip())
            i = max(i, cut - overlap)
        else:
            chunks.append(text[i:end].strip())
            i = max(i, end - overlap)
        if i >= len(text):
            break


def _final_pass(chunks: list, chunk_size: int) -> List[str]:
    result = []
    for ch in chunks:
        if len(ch) <= chunk_size * 1.5:
            result.append(ch)
            continue
        i = 0
        while i < len(ch):
            end = min(i + chunk_size, len(ch))
            result.append(ch[i:end].strip())
            i += chunk_size
    return result


def chunk_single_document(doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> List[dict]:
    """对单个文档切片，生成带元数据的 chunk 列表"""
    doc_hash = content_hash(doc["text"])
    chunks = split_text(doc["text"], chunk_cfg)
    result = []

    source_path = doc["path"]
    if source_type == "web_crawl":
        source_name = doc.get("title", source_path)
    else:
        source_name = Path(source_path).name

    for i, chunk in enumerate(chunks):
        result.append({
            "id": f"{md5_short(source_path)}-{i}",
            "text": chunk,
            "source": source_path,
            "source_type": source_type,
            "source_name": source_name,
            "chunk_index": i,
            "content_hash": doc_hash,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result

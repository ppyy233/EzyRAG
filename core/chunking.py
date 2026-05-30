# -*- coding: utf-8 -*-
"""
Ezy-RAG — 文本切分模块
提供多种文本切分策略
"""
from datetime import datetime
from pathlib import Path
from typing import List

from core.utils import content_hash, md5_short


def split_text(text: str, cfg: dict) -> List[str]:
    """按模板配置切片"""
    chunk_size = cfg["chunk_size"]
    overlap = cfg["overlap"]
    strategy = cfg.get("strategy", "flat")
    separators = cfg["separators"]
    if strategy == "recursive":
        return _split_recursive(text, chunk_size, overlap, separators)
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

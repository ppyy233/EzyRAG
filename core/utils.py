# -*- coding: utf-8 -*-
"""
Ezy-RAG — 工具函数模块
提供通用的哈希和辅助函数
"""
import hashlib


def content_hash(text: str) -> str:
    """计算文本的 MD5 哈希值"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def md5_short(text: str) -> str:
    """计算文本的短 MD5 哈希值（前 12 位）"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]

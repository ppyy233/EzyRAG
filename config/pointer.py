# -*- coding: utf-8 -*-
"""
Ezy-RAG — 指针管理模块
管理 collection_pointer.json，实现原子写入
指针文件记录当前活跃的集合名，格式：
{
  "default_collection": "default_collection_v20260527_192848"
}
"""
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POINTER_FILE = ROOT / "runtime" / "state" / "collection_pointer.json"


def read_pointer() -> dict:
    """读取指针文件"""
    if POINTER_FILE.exists():
        with open(POINTER_FILE, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}


def write_pointer(data: dict):
    """原子写入指针文件（临时文件 + os.replace）"""
    POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POINTER_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(POINTER_FILE))


def get_active_collection(config_key: str) -> str:
    """获取活跃集合名，没有则回退到 config_key 本身"""
    p = read_pointer()
    return p.get(config_key, config_key)


def set_active_collection(config_key: str, name: str):
    """设置活跃集合名"""
    p = read_pointer()
    p[config_key] = name
    write_pointer(p)

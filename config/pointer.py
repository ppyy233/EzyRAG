# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?鎸囬拡绠＄悊妯″潡
绠＄悊 collection_pointer.json锛屽疄鐜板師瀛愬啓鍏?
鎸囬拡鏂囦欢璁板綍褰撳墠娲昏穬鐨勯泦鍚堝悕锛屾牸寮忥細
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
    """璇诲彇鎸囬拡鏂囦欢"""
    if POINTER_FILE.exists():
        with open(POINTER_FILE, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}


def write_pointer(data: dict):
    """鍘熷瓙鍐欏叆鎸囬拡鏂囦欢锛堜复鏃舵枃浠?+ os.replace锛?""
    POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POINTER_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(POINTER_FILE))


def get_active_collection(config_key: str) -> str:
    """鑾峰彇娲昏穬闆嗗悎鍚嶏紝娌℃湁鍒欏洖閫€鍒?config_key 鏈韩"""
    p = read_pointer()
    return p.get(config_key, config_key)


def set_active_collection(config_key: str, name: str):
    """璁剧疆娲昏穬闆嗗悎鍚?""
    p = read_pointer()
    p[config_key] = name
    write_pointer(p)

# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?閰嶇疆绠＄悊
鍙傝€冨墠绔璁＄殑绠€娲侀厤缃鐞嗙晫闈?"""
import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import header, info_card, menu, confirm, log_ok, log_error, log_info, log_step
from cli.cli_core import reload_env

CONFIG_DIR = ROOT / "config"
ENV_FILE = CONFIG_DIR / ".env"
ENV_EXAMPLE = CONFIG_DIR / ".env.example"


def load_env() -> dict:
    """鍔犺浇 .env 鏂囦欢"""
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip()
    return env


def save_env(env: dict):
    """淇濆瓨 .env 鏂囦欢"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write("# ============================================================\n")
        f.write("# Ezy-RAG 鈥?鐜閰嶇疆\n")
        f.write("# ============================================================\n\n")
        
        f.write("# ----- Embedding 閰嶇疆 -----\n")
        f.write(f"EMBEDDING_MODE={env.get('EMBEDDING_MODE', 'cloud')}\n\n")
        f.write("# 浜戠閰嶇疆\n")
        for key in ['EMBEDDING_CLOUD_URL', 'EMBEDDING_CLOUD_API_KEY', 'EMBEDDING_CLOUD_MODEL', 'EMBEDDING_CLOUD_DIM']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n# 鏈湴閰嶇疆\n")
        for key in ['EMBEDDING_LOCAL_URL', 'EMBEDDING_LOCAL_MODEL_PATH', 'EMBEDDING_LOCAL_DIM']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- Rerank 閰嶇疆 -----\n")
        f.write(f"RERANK_ENABLED={env.get('RERANK_ENABLED', 'true')}\n")
        f.write(f"RERANK_MODE={env.get('RERANK_MODE', 'local')}\n\n")
        f.write("# 浜戠閰嶇疆\n")
        for key in ['RERANK_CLOUD_URL', 'RERANK_CLOUD_API_KEY', 'RERANK_CLOUD_MODEL']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n# 鏈湴閰嶇疆\n")
        for key in ['RERANK_LOCAL_URL', 'RERANK_LOCAL_MODEL_PATH']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- 鏈嶅姟閰嶇疆 -----\n")
        for key in ['CHROMA_SERVER_HOST', 'CHROMA_SERVER_PORT', 'MCP_SERVER_HOST', 'MCP_SERVER_PORT']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- 鍒囧潡绛栫暐 -----\n")
        f.write(f"CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}\n")
    
    reload_env()


def show_config():
    """鏄剧ず褰撳墠閰嶇疆"""
    env = load_env()
    
    # Embedding 閰嶇疆
    embedding_mode = env.get('EMBEDDING_MODE', 'cloud')
    if embedding_mode == 'cloud':
        embedding_info = {
            "妯″紡": "cloud (浜戠)",
            "URL": env.get('EMBEDDING_CLOUD_URL', '-'),
            "妯″瀷": env.get('EMBEDDING_CLOUD_MODEL', '-'),
            "API Key": "****" + env.get('EMBEDDING_CLOUD_API_KEY', '')[-4:] if env.get('EMBEDDING_CLOUD_API_KEY') else '-',
        }
    else:
        embedding_info = {
            "妯″紡": "local (鏈湴)",
            "URL": env.get('EMBEDDING_LOCAL_URL', '-'),
            "妯″瀷璺緞": env.get('EMBEDDING_LOCAL_MODEL_PATH', '-'),
        }
    info_card("Embedding 閰嶇疆", embedding_info)
    
    # Rerank 閰嶇疆
    rerank_enabled = env.get('RERANK_ENABLED', 'true').lower() == 'true'
    rerank_mode = env.get('RERANK_MODE', 'local')
    if not rerank_enabled:
        rerank_info = {"鍚敤": "false (鏈惎鐢?"}
    elif rerank_mode == 'cloud':
        rerank_info = {
            "鍚敤": "true",
            "妯″紡": "cloud (浜戠)",
            "URL": env.get('RERANK_CLOUD_URL', '-'),
            "妯″瀷": env.get('RERANK_CLOUD_MODEL', '-'),
        }
    else:
        rerank_info = {
            "鍚敤": "true",
            "妯″紡": "local (鏈湴)",
            "URL": env.get('RERANK_LOCAL_URL', '-'),
        }
    info_card("Rerank 閰嶇疆", rerank_info)
    
    # 鏈嶅姟閰嶇疆
    info_card("鏈嶅姟閰嶇疆", {
        "ChromaDB": f"{env.get('CHROMA_SERVER_HOST', '127.0.0.1')}:{env.get('CHROMA_SERVER_PORT', '9898')}",
        "MCP": f"{env.get('MCP_SERVER_HOST', '127.0.0.1')}:{env.get('MCP_SERVER_PORT', '9766')}",
    })
    
    # 鍒囧潡绛栫暐
    info_card("鍒囧潡绛栫暐", {
        "妯℃澘": env.get('CHUNK_TEMPLATE', 'academic'),
    })


def modify_embedding():
    """淇敼 Embedding 閰嶇疆"""
    env = load_env()
    
    log_step("淇敼 Embedding 閰嶇疆")
    print("  褰撳墠妯″紡:", env.get('EMBEDDING_MODE', 'cloud'))
    print()
    print("  1. cloud (浜戠)")
    print("  2. local (鏈湴)")
    
    choice = input("\n  閫夋嫨妯″紡 (1-2, 鐩存帴鍥炶溅璺宠繃): ").strip()
    
    if choice == '1':
        env['EMBEDDING_MODE'] = 'cloud'
        print(f"\n  褰撳墠 URL: {env.get('EMBEDDING_CLOUD_URL', 'https://api.siliconflow.cn/v1/embeddings')}")
        url = input("  鏂?URL (鐩存帴鍥炶溅璺宠繃): ").strip()
        if url:
            env['EMBEDDING_CLOUD_URL'] = url
        
        print(f"\n  褰撳墠妯″瀷: {env.get('EMBEDDING_CLOUD_MODEL', 'BAAI/bge-m3')}")
        model = input("  鏂版ā鍨?(鐩存帴鍥炶溅璺宠繃): ").strip()
        if model:
            env['EMBEDDING_CLOUD_MODEL'] = model
        
        print(f"\n  褰撳墠 API Key: ****{env.get('EMBEDDING_CLOUD_API_KEY', '')[-4:]}" if env.get('EMBEDDING_CLOUD_API_KEY') else "\n  褰撳墠 API Key: 鏈缃?)
        api_key = input("  鏂?API Key (鐩存帴鍥炶溅璺宠繃): ").strip()
        if api_key:
            env['EMBEDDING_CLOUD_API_KEY'] = api_key
        
    elif choice == '2':
        env['EMBEDDING_MODE'] = 'local'
        print(f"\n  褰撳墠 URL: {env.get('EMBEDDING_LOCAL_URL', 'http://127.0.0.1:1234/v1/embeddings')}")
        url = input("  鏂?URL (鐩存帴鍥炶溅璺宠繃): ").strip()
        if url:
            env['EMBEDDING_LOCAL_URL'] = url
        
        print(f"\n  褰撳墠妯″瀷璺緞: {env.get('EMBEDDING_LOCAL_MODEL_PATH', 'data/models/embedding')}")
        path = input("  鏂版ā鍨嬭矾寰?(鐩存帴鍥炶溅璺宠繃): ").strip()
        if path:
            env['EMBEDDING_LOCAL_MODEL_PATH'] = path
    
    else:
        return
    
    save_env(env)
    log_ok("Embedding 閰嶇疆宸蹭繚瀛?)


def modify_rerank():
    """淇敼 Rerank 閰嶇疆"""
    env = load_env()
    
    log_step("淇敼 Rerank 閰嶇疆")
    print("  褰撳墠鍚敤:", env.get('RERANK_ENABLED', 'true'))
    print()
    print("  1. 鍚敤")
    print("  2. 绂佺敤")
    
    choice = input("\n  閫夋嫨 (1-2, 鐩存帴鍥炶溅璺宠繃): ").strip()
    
    if choice == '1':
        env['RERANK_ENABLED'] = 'true'
        
        print(f"\n  褰撳墠妯″紡: {env.get('RERANK_MODE', 'local')}")
        print("  1. cloud (浜戠)")
        print("  2. local (鏈湴)")
        mode_choice = input("  閫夋嫨妯″紡 (1-2, 鐩存帴鍥炶溅璺宠繃): ").strip()
        
        if mode_choice == '1':
            env['RERANK_MODE'] = 'cloud'
            print(f"\n  褰撳墠 URL: {env.get('RERANK_CLOUD_URL', 'https://api.siliconflow.cn/v1/rerank')}")
            url = input("  鏂?URL (鐩存帴鍥炶溅璺宠繃): ").strip()
            if url:
                env['RERANK_CLOUD_URL'] = url
            
            print(f"\n  褰撳墠妯″瀷: {env.get('RERANK_CLOUD_MODEL', 'BAAI/bge-reranker-v2-m3')}")
            model = input("  鏂版ā鍨?(鐩存帴鍥炶溅璺宠繃): ").strip()
            if model:
                env['RERANK_CLOUD_MODEL'] = model
            
            print(f"\n  褰撳墠 API Key: ****{env.get('RERANK_CLOUD_API_KEY', '')[-4:]}" if env.get('RERANK_CLOUD_API_KEY') else "\n  褰撳墠 API Key: 鏈缃?)
            api_key = input("  鏂?API Key (鐩存帴鍥炶溅璺宠繃): ").strip()
            if api_key:
                env['RERANK_CLOUD_API_KEY'] = api_key
            
        elif mode_choice == '2':
            env['RERANK_MODE'] = 'local'
            print(f"\n  褰撳墠 URL: {env.get('RERANK_LOCAL_URL', 'http://127.0.0.1:5001')}")
            url = input("  鏂?URL (鐩存帴鍥炶溅璺宠繃): ").strip()
            if url:
                env['RERANK_LOCAL_URL'] = url
        
        else:
            return
        
    elif choice == '2':
        env['RERANK_ENABLED'] = 'false'
    
    else:
        return
    
    save_env(env)
    log_ok("Rerank 閰嶇疆宸蹭繚瀛?)


def modify_chunk():
    """淇敼鍒囧潡绛栫暐"""
    from config.settings import get_chunk_templates
    
    env = load_env()
    templates = get_chunk_templates()
    
    log_step("淇敼鍒囧潡绛栫暐")
    print(f"  褰撳墠妯℃澘: {env.get('CHUNK_TEMPLATE', 'academic')}")
    print()
    
    template_list = list(templates.keys())
    for i, name in enumerate(template_list, 1):
        t = templates[name]
        print(f"  {i}. {name} - {t['name']} (chunk_size={t['chunk_size']}, overlap={t['overlap']})")
    
    choice = input(f"\n  閫夋嫨妯℃澘 (1-{len(template_list)}, 鐩存帴鍥炶溅璺宠繃): ").strip()
    
    if choice and choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(template_list):
            env['CHUNK_TEMPLATE'] = template_list[idx]
            save_env(env)
            log_ok(f"鍒囧潡妯℃澘宸茶缃负: {template_list[idx]}")
        else:
            log_error("鏃犳晥鐨勯€夋嫨")
    elif choice:
        log_error("鏃犳晥鐨勯€夋嫨")


def reset_config():
    """閲嶇疆閰嶇疆涓洪粯璁ゅ€?""
    if not confirm("纭畾瑕侀噸缃厤缃负榛樿鍊硷紵褰撳墠閰嶇疆灏嗚瑕嗙洊", default=False):
        return
    
    if ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        reload_env()
        log_ok("閰嶇疆宸查噸缃负榛樿鍊?)
    else:
        log_error("鎵句笉鍒伴粯璁ら厤缃枃浠? config/.env.example")


def main():
    """涓诲嚱鏁?""
    while True:
        header("Ezy-RAG 閰嶇疆绠＄悊")
        
        # 鏄剧ず褰撳墠閰嶇疆
        show_config()
        
        # 鑿滃崟
        choice = menu("鎿嶄綔", [
            "淇敼 Embedding 閰嶇疆",
            "淇敼 Rerank 閰嶇疆",
            "淇敼鍒囧潡绛栫暐",
            "閲嶇疆閰嶇疆",
            "杩斿洖"
        ])
        
        if choice == 1:
            modify_embedding()
        elif choice == 2:
            modify_rerank()
        elif choice == 3:
            modify_chunk()
        elif choice == 4:
            reset_config()
        elif choice == 5:
            break
        
        if choice != 5:
            from cli.ui import pause
            pause()


if __name__ == "__main__":
    main()

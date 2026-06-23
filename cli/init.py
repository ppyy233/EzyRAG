# -*- coding: utf-8 -*-
"""
Ezy-RAG — 配置管理
参考前端设计的简洁配置管理界面"""
import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import header, info_card, menu, confirm, log_ok, log_error, log_info, log_step
from cli.cli_core import reload_env
from config.version import VERSION_DISPLAY

CONFIG_DIR = ROOT / "config"
ENV_FILE = CONFIG_DIR / ".env"
ENV_EXAMPLE = CONFIG_DIR / ".env.example"


def load_env() -> dict:
    """加载 .env 文件"""
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
    """保存 .env 文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write("# ============================================================\n")
        f.write(f"# Ezy-RAG {VERSION_DISPLAY} — 环境配置\n")
        f.write("# ============================================================\n\n")
        
        f.write("# ----- Embedding 配置 -----\n")
        f.write(f"EMBEDDING_MODE={env.get('EMBEDDING_MODE', 'cloud')}\n\n")
        f.write("# 云端配置\n")
        for key in ['EMBEDDING_CLOUD_URL', 'EMBEDDING_CLOUD_API_KEY', 'EMBEDDING_CLOUD_MODEL', 'EMBEDDING_CLOUD_DIM']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n# 本地配置\n")
        for key in ['EMBEDDING_LOCAL_URL', 'EMBEDDING_LOCAL_MODEL_PATH', 'EMBEDDING_LOCAL_DIM']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- Rerank 配置 -----\n")
        f.write(f"RERANK_ENABLED={env.get('RERANK_ENABLED', 'true')}\n")
        f.write(f"RERANK_MODE={env.get('RERANK_MODE', 'cloud')}\n\n")
        f.write("# 云端配置\n")
        for key in ['RERANK_CLOUD_URL', 'RERANK_CLOUD_API_KEY', 'RERANK_CLOUD_MODEL']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n# 本地配置\n")
        for key in ['RERANK_LOCAL_URL', 'RERANK_LOCAL_MODEL_PATH']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- 服务配置 -----\n")
        for key in ['CHROMA_SERVER_HOST', 'CHROMA_SERVER_PORT', 'MCP_SERVER_HOST', 'MCP_SERVER_PORT', 'WEB_API_HOST', 'WEB_API_PORT']:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        
        f.write("# ----- 切块策略 -----\n")
        f.write(f"CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}\n")
    
    reload_env()


def show_config():
    """显示当前配置"""
    env = load_env()
    
    # Embedding 配置
    embedding_mode = env.get('EMBEDDING_MODE', 'cloud')
    if embedding_mode == 'cloud':
        embedding_info = {
            "模式": "cloud (云端)",
            "URL": env.get('EMBEDDING_CLOUD_URL', '-'),
            "模型": env.get('EMBEDDING_CLOUD_MODEL', '-'),
            "API Key": "****" + env.get('EMBEDDING_CLOUD_API_KEY', '')[-4:] if env.get('EMBEDDING_CLOUD_API_KEY') else '-',
        }
    else:
        embedding_info = {
            "模式": "local (本地)",
            "URL": env.get('EMBEDDING_LOCAL_URL', '-'),
            "模型路径": env.get('EMBEDDING_LOCAL_MODEL_PATH', '-'),
        }
    info_card("Embedding 配置", embedding_info)
    
    # Rerank 配置
    rerank_enabled = env.get('RERANK_ENABLED', 'true').lower() == 'true'
    rerank_mode = env.get('RERANK_MODE', 'cloud')
    if not rerank_enabled:
        rerank_info = {"启用": "false (未启用)"}
    elif rerank_mode == 'cloud':
        rerank_info = {
            "启用": "true",
            "模式": "cloud (云端)",
            "URL": env.get('RERANK_CLOUD_URL', '-'),
            "模型": env.get('RERANK_CLOUD_MODEL', '-'),
        }
    else:
        rerank_info = {
            "启用": "true",
            "模式": "local (本地)",
            "URL": env.get('RERANK_LOCAL_URL', '-'),
        }
    info_card("Rerank 配置", rerank_info)
    
    # 服务配置
    info_card("服务配置", {
        "ChromaDB": f"{env.get('CHROMA_SERVER_HOST', '127.0.0.1')}:{env.get('CHROMA_SERVER_PORT', '9898')}",
        "MCP": f"{env.get('MCP_SERVER_HOST', '127.0.0.1')}:{env.get('MCP_SERVER_PORT', '9766')}",
        "Web": f"{env.get('WEB_API_HOST', '127.0.0.1')}:{env.get('WEB_API_PORT', '9767')}",
    })
    
    # 切块策略
    from config.settings import get_chunk_config
    chunk_cfg = get_chunk_config()
    info_card("切块策略", {
        "模板": env.get('CHUNK_TEMPLATE', 'academic'),
        "策略": chunk_cfg.get('strategy', '-'),
        "chunk_size": str(chunk_cfg.get('chunk_size', '-')),
        "overlap": str(chunk_cfg.get('overlap', '-')),
    })


def modify_embedding():
    """修改 Embedding 配置"""
    env = load_env()
    
    log_step("修改 Embedding 配置")
    print("  当前模式:", env.get('EMBEDDING_MODE', 'cloud'))
    print()
    print("  1. cloud (云端)")
    print("  2. local (本地)")
    
    choice = input("\n  选择模式 (1-2, 直接回车跳过): ").strip()
    
    if choice == '1':
        env['EMBEDDING_MODE'] = 'cloud'
        print(f"\n  当前 URL: {env.get('EMBEDDING_CLOUD_URL', 'https://api.siliconflow.cn/v1/embeddings')}")
        url = input("  新 URL (直接回车跳过): ").strip()
        if url:
            env['EMBEDDING_CLOUD_URL'] = url
        
        print(f"\n  当前模型: {env.get('EMBEDDING_CLOUD_MODEL', 'BAAI/bge-m3')}")
        model = input("  新模型 (直接回车跳过): ").strip()
        if model:
            env['EMBEDDING_CLOUD_MODEL'] = model
        
        print(f"\n  当前 API Key: ****{env.get('EMBEDDING_CLOUD_API_KEY', '')[-4:]}" if env.get('EMBEDDING_CLOUD_API_KEY') else "\n  当前 API Key: 未设置")
        api_key = input("  新 API Key (直接回车跳过): ").strip()
        if api_key:
            env['EMBEDDING_CLOUD_API_KEY'] = api_key
        
    elif choice == '2':
        env['EMBEDDING_MODE'] = 'local'
        print(f"\n  当前 URL: {env.get('EMBEDDING_LOCAL_URL', 'http://127.0.0.1:1234/v1/embeddings')}")
        url = input("  新 URL (直接回车跳过): ").strip()
        if url:
            env['EMBEDDING_LOCAL_URL'] = url
        
        print(f"\n  当前模型路径: {env.get('EMBEDDING_LOCAL_MODEL_PATH', 'data/models/embedding')}")
        path = input("  新模型路径 (直接回车跳过): ").strip()
        if path:
            env['EMBEDDING_LOCAL_MODEL_PATH'] = path
    
    else:
        return
    
    save_env(env)
    log_ok("Embedding 配置已保存")


def modify_rerank():
    """修改 Rerank 配置"""
    env = load_env()
    
    log_step("修改 Rerank 配置")
    print("  当前启用:", env.get('RERANK_ENABLED', 'true'))
    print()
    print("  1. 启用")
    print("  2. 禁用")
    
    choice = input("\n  选择 (1-2, 直接回车跳过): ").strip()
    
    if choice == '1':
        env['RERANK_ENABLED'] = 'true'
        
        print(f"\n  当前模式: {env.get('RERANK_MODE', 'cloud')}")
        print("  1. cloud (云端)")
        print("  2. local (本地)")
        mode_choice = input("  选择模式 (1-2, 直接回车跳过): ").strip()
        
        if mode_choice == '1':
            env['RERANK_MODE'] = 'cloud'
            print(f"\n  当前 URL: {env.get('RERANK_CLOUD_URL', 'https://api.siliconflow.cn/v1/rerank')}")
            url = input("  新 URL (直接回车跳过): ").strip()
            if url:
                env['RERANK_CLOUD_URL'] = url
            
            print(f"\n  当前模型: {env.get('RERANK_CLOUD_MODEL', 'BAAI/bge-reranker-v2-m3')}")
            model = input("  新模型 (直接回车跳过): ").strip()
            if model:
                env['RERANK_CLOUD_MODEL'] = model
            
            print(f"\n  当前 API Key: ****{env.get('RERANK_CLOUD_API_KEY', '')[-4:]}" if env.get('RERANK_CLOUD_API_KEY') else "\n  当前 API Key: 未设置")
            api_key = input("  新 API Key (直接回车跳过): ").strip()
            if api_key:
                env['RERANK_CLOUD_API_KEY'] = api_key
            
        elif mode_choice == '2':
            env['RERANK_MODE'] = 'local'
            print(f"\n  当前 URL: {env.get('RERANK_LOCAL_URL', 'http://127.0.0.1:5001')}")
            url = input("  新 URL (直接回车跳过): ").strip()
            if url:
                env['RERANK_LOCAL_URL'] = url
        
        else:
            return
        
    elif choice == '2':
        env['RERANK_ENABLED'] = 'false'
    
    else:
        return
    
    save_env(env)
    log_ok("Rerank 配置已保存")


def modify_chunk():
    """修改切块策略"""
    from config.settings import get_chunk_templates, save_config, load_config
    
    env = load_env()
    templates = get_chunk_templates()
    
    log_step("修改切块策略")
    current = env.get('CHUNK_TEMPLATE', 'academic')
    print(f"  当前模板: {current}")
    print()
    
    template_list = list(templates.keys())
    for i, name in enumerate(template_list, 1):
        t = templates[name]
        strategy = t.get('strategy', 'flat')
        separators_count = len(t.get('separators', []))
        print(f"  {i}. {name} - {t['name']}")
        print(f"     chunk_size={t['chunk_size']}, overlap={t['overlap']}, strategy={strategy}, separators={separators_count}个")
    
    print(f"\n  {len(template_list) + 1}. 自定义参数（修改当前模板的参数）")
    
    choice = input(f"\n  选择 (1-{len(template_list) + 1}, 直接回车跳过): ").strip()
    
    if choice and choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(template_list):
            # 切换到预设模板
            env['CHUNK_TEMPLATE'] = template_list[idx]
            save_env(env)
            # 同步更新 config.json 的 default_template
            config = load_config()
            config["chunk"]["default_template"] = template_list[idx]
            save_config(config)
            log_ok(f"切块模板已设置为: {template_list[idx]}")
        elif idx == len(template_list):
            # 自定义参数
            _customize_chunk_params(env, templates)
        else:
            log_error("无效的选择")
    elif choice:
        log_error("无效的选择")


def _customize_chunk_params(env: dict, templates: dict):
    """自定义切块参数"""
    from config.settings import save_config, load_config
    
    current = env.get('CHUNK_TEMPLATE', 'academic')
    current_template = templates.get(current, {})
    
    print(f"\n  当前模板: {current}")
    print(f"  当前参数: chunk_size={current_template.get('chunk_size', '-')}, overlap={current_template.get('overlap', '-')}, strategy={current_template.get('strategy', '-')}")
    print()
    
    # chunk_size
    chunk_size_str = input(f"  chunk_size [{current_template.get('chunk_size', 1000)}]: ").strip()
    if chunk_size_str and chunk_size_str.isdigit():
        chunk_size = int(chunk_size_str)
    else:
        chunk_size = current_template.get('chunk_size', 1000)
    
    # overlap
    overlap_str = input(f"  overlap [{current_template.get('overlap', 100)}]: ").strip()
    if overlap_str and overlap_str.isdigit():
        overlap = int(overlap_str)
    else:
        overlap = current_template.get('overlap', 100)
    
    # strategy
    print(f"\n  可用策略:")
    print(f"    1. recursive - 递归切分（适合文档）")
    print(f"    2. flat - 扁平切分（适合代码）")
    print(f"    3. sentence - 句子级切分（适合FAQ）")
    print(f"    4. markdown_header - Markdown标题切分")
    
    strategy_map = {'1': 'recursive', '2': 'flat', '3': 'sentence', '4': 'markdown_header'}
    current_strategy = current_template.get('strategy', 'recursive')
    strategy_choice = input(f"  strategy [{current_strategy}]: ").strip()
    
    if strategy_choice in strategy_map:
        strategy = strategy_map[strategy_choice]
    elif strategy_choice in strategy_map.values():
        strategy = strategy_choice
    else:
        strategy = current_strategy
    
    # 确认
    print(f"\n  新参数: chunk_size={chunk_size}, overlap={overlap}, strategy={strategy}")
    confirm_choice = input("  确认保存? (Y/n): ").strip().lower()
    
    if confirm_choice != 'n':
        # 更新 config.json 中的 custom 模板
        config = load_config()
        config["chunk"]["templates"]["custom"] = {
            "name": "自定义模板",
            "chunk_size": chunk_size,
            "overlap": overlap,
            "strategy": strategy,
            "separators": ["\n\n", "\n", " ", ""]
        }
        config["chunk"]["default_template"] = "custom"
        save_config(config)
        
        # 更新 .env
        env['CHUNK_TEMPLATE'] = 'custom'
        save_env(env)
        
        log_ok("自定义切块参数已保存")


def modify_services():
    """修改服务端口配置"""
    env = load_env()
    
    log_step("修改服务端口")
    print(f"  当前配置:")
    print(f"  1. ChromaDB: {env.get('CHROMA_SERVER_HOST', '127.0.0.1')}:{env.get('CHROMA_SERVER_PORT', '9898')}")
    print(f"  2. MCP:      {env.get('MCP_SERVER_HOST', '127.0.0.1')}:{env.get('MCP_SERVER_PORT', '9766')}")
    print(f"  3. Web:      {env.get('WEB_API_HOST', '127.0.0.1')}:{env.get('WEB_API_PORT', '9767')}")
    print()
    
    choice = input("  选择要修改的服务 (1-3, 直接回车跳过): ").strip()
    
    if choice == '1':
        host = input(f"  Host [{env.get('CHROMA_SERVER_HOST', '127.0.0.1')}]: ").strip()
        if host: env['CHROMA_SERVER_HOST'] = host
        port = input(f"  Port [{env.get('CHROMA_SERVER_PORT', '9898')}]: ").strip()
        if port: env['CHROMA_SERVER_PORT'] = port
    elif choice == '2':
        host = input(f"  Host [{env.get('MCP_SERVER_HOST', '127.0.0.1')}]: ").strip()
        if host: env['MCP_SERVER_HOST'] = host
        port = input(f"  Port [{env.get('MCP_SERVER_PORT', '9766')}]: ").strip()
        if port: env['MCP_SERVER_PORT'] = port
    elif choice == '3':
        host = input(f"  Host [{env.get('WEB_API_HOST', '127.0.0.1')}]: ").strip()
        if host: env['WEB_API_HOST'] = host
        port = input(f"  Port [{env.get('WEB_API_PORT', '9767')}]: ").strip()
        if port: env['WEB_API_PORT'] = port
    else:
        return
    
    save_env(env)
    log_ok("服务配置已保存")


def reset_config():
    """重置配置为默认值"""
    if not confirm("确定要重置配置为默认值？当前配置将被覆盖", default=False):
        return
    
    if ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        reload_env()
        log_ok("配置已重置为默认值")
    else:
        log_error("找不到默认配置文件: config/.env.example")


def main():
    """主函数"""
    while True:
        header("Ezy-RAG 配置管理")
        
        # 显示当前配置
        show_config()
        
        # 菜单
        choice = menu("操作", [
            "修改 Embedding 配置",
            "修改 Rerank 配置",
            "修改服务端口",
            "修改切块策略",
            "重置配置",
            "返回"
        ])
        
        if choice == 1:
            modify_embedding()
        elif choice == 2:
            modify_rerank()
        elif choice == 3:
            modify_services()
        elif choice == 4:
            modify_chunk()
        elif choice == 5:
            reset_config()
        elif choice == 6:
            break
        
        if choice != 6:
            from cli.ui import pause
            pause()


if __name__ == "__main__":
    main()

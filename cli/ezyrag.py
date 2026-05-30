# -*- coding: utf-8 -*-
"""
Ezy-RAG — 统一命令行入口
用法: python ezyrag.py [command]

命令：
  service              服务管理
  db                   文档管理
  config               配置管理
  health               健康检查
  quickstart           快速开始向导

示例：
  python ezyrag.py                 # 交互式菜单
  python ezyrag.py service         # 服务管理
  python ezyrag.py db              # 文档管理
  python ezyrag.py config          # 配置管理
  python ezyrag.py health          # 健康检�?"""
import os
import sys
import subprocess
from pathlib import Path

# Windows 终端编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import header, status_card, info_card, menu, confirm, log_ok, log_error, log_info, log_step


def check_environment() -> bool:
    """检查环境是否就�?""
    log_step("环境检�?)
    
    # 检�?Python 版本
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        log_error(f"Python {version.major}.{version.minor}.{version.micro} (需�?>= 3.11)")
        return False
    log_ok(f"Python {version.major}.{version.minor}.{version.micro}")
    
    # 检�?uv
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True, cwd=ROOT)
        if result.returncode == 0:
            log_ok("uv 已安�?)
        else:
            log_error("uv 未安�?)
            return False
    except FileNotFoundError:
        log_error("uv 未安�?)
        return False
    
    # 检�?.env
    env_file = ROOT / "config" / ".env"
    if env_file.exists():
        log_ok("config/.env 已存�?)
    else:
        log_info("config/.env 不存在（将从模板创建�?)
    
    return True


def cmd_quickstart():
    """快速开始向�?""
    header("Ezy-RAG Quick Start 向导")
    
    # Step 1: 环境检�?    if not check_environment():
        log_error("环境检查未通过，请先解决上述问�?)
        return
    
    # Step 2: 安装依赖
    log_step("安装依赖")
    if not (ROOT / ".venv").exists():
        log_info("正在创建虚拟环境...")
        result = subprocess.run(["uv", "venv"], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            log_error(f"创建虚拟环境失败: {result.stderr}")
            return
        log_ok("虚拟环境已创�?)
    
    log_info("正在安装依赖...")
    result = subprocess.run(["uv", "sync"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        log_error(f"安装依赖失败: {result.stderr}")
        return
    log_ok("依赖已安�?)
    
    # Step 3: 配置
    log_step("配置")
    if not (ROOT / "config" / ".env").exists():
        log_info("即将启动配置向导...")
        subprocess.run([sys.executable, "cli/init.py"], cwd=ROOT)
    else:
        log_info("配置文件已存在，跳过")
    
    # Step 4: 添加本地文档（可选）
    log_step("添加本地文档")
    docs_dir = ROOT / "data" / "docs"
    if docs_dir.exists():
        doc_count = 0
        for ext in [".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts"]:
            doc_count += len(list(docs_dir.glob(f"**/*{ext}")))
        
        if doc_count > 0:
            log_info(f"发现 {doc_count} 个本地文�?)
            if confirm("是否添加到向量库�?, default=True):
                subprocess.run([sys.executable, "cli/db_manage.py"], cwd=ROOT)
            else:
                log_info("跳过添加文档")
        else:
            log_info("data/docs/ 目录为空，跳过添加文�?)
    else:
        log_info("data/docs/ 目录不存在，跳过添加文档")
    
    # Step 5: 启动服务
    log_step("启动服务")
    log_info("即将启动服务管理...")
    subprocess.run([sys.executable, "cli/start_all.py"], cwd=ROOT)
    
    # 完成
    header("Quick Start 完成�?)
    print("\n  下一步操�?")
    log_info("python ezyrag.py service      # 服务管理")
    log_info("python ezyrag.py db           # 文档管理")
    log_info("python ezyrag.py config       # 配置管理")
    log_info("python ezyrag.py health       # 健康检�?)


def cmd_health():
    """健康检�?""
    from cli.cli_core import get_service_status, get_database_stats
    
    header("Ezy-RAG 健康检�?)
    
    # 服务状�?    status = get_service_status()
    services_display = [
        {"name": "ChromaDB", "online": status["chromadb"]["online"], "info": status["chromadb"]["info"]},
        {"name": "Embedding", "online": status["embedding"]["online"], "info": status["embedding"]["info"]},
        {"name": "Rerank", "online": status["rerank"]["online"], "info": status["rerank"]["info"], "skip": status["rerank"].get("skip", False)},
        {"name": "MCP", "online": status["mcp"]["online"], "info": status["mcp"]["info"]},
    ]
    status_card(services_display)
    
    # 数据库状�?    stats = get_database_stats()
    info_card("数据库状�?, {
        "本地文档": f"{stats['docs_count']} �?,
        "网页数据": f"{stats['web_count']} �?,
        "已导�?: f"{stats['vector_docs']} �?,
        "向量�?: f"{stats['chunks']} �?,
        "集合": stats['collection'] or "-"
    })


def cmd_service():
    """服务管理"""
    subprocess.run([sys.executable, "cli/start_all.py"], cwd=ROOT)


def cmd_db():
    """文档管理"""
    subprocess.run([sys.executable, "cli/db_manage.py"], cwd=ROOT)


def cmd_config():
    """配置管理"""
    subprocess.run([sys.executable, "cli/init.py"], cwd=ROOT)


def show_help():
    """显示帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════╗
�? Ezy-RAG V1.0.0 �?知识库系�?                               �?╚══════════════════════════════════════════════════════════════╝

用法�?  python ezyrag.py [command]

命令�?  quickstart          快速开始向导（首次使用�?  service             服务管理
  db                  文档管理
  config              配置管理
  health              健康检�?  help                显示此帮�?
首次使用�?  python ezyrag.py quickstart         # 一键初始化

常用工作流：
  1. python ezyrag.py quickstart      # 初始化配�?  2. python ezyrag.py db              # 添加文档
  3. python ezyrag.py service         # 启动服务
  4. python ezyrag.py health          # 检查状�?""")


def main():
    """主函�?""
    args = sys.argv[1:]
    
    if not args:
        # 无参数，显示交互式菜�?        while True:
            header("Ezy-RAG V1.0.0 知识库系�?)
            
            choice = menu("功能", [
                "快速开�?,
                "服务管理",
                "文档管理",
                "配置管理",
                "健康检�?,
                "退�?
            ])
            
            if choice == 1:
                cmd_quickstart()
            elif choice == 2:
                cmd_service()
            elif choice == 3:
                cmd_db()
            elif choice == 4:
                cmd_config()
            elif choice == 5:
                cmd_health()
            elif choice == 6:
                break
            
            if choice != 6:
                from cli.ui import pause
                pause()
        return
    
    # 有参数，解析命令
    command = args[0].lower()
    
    if command == "quickstart":
        cmd_quickstart()
    elif command == "service":
        cmd_service()
    elif command == "db":
        cmd_db()
    elif command == "config":
        cmd_config()
    elif command == "health":
        cmd_health()
    elif command in ["help", "--help", "-h"]:
        show_help()
    else:
        log_error(f"未知命令: {command}")
        print(f"  使用 'python ezyrag.py help' 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()

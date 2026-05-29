# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.18 — 统一命令行入口
用法: python ezyrag.py <command> [args...]

命令：
  quickstart          快速开始向导
  init                配置管理
  service             服务管理
  db <args>           数据库管理
  build [args]        知识库构建
  health              健康检查

示例：
  python ezyrag.py quickstart           # 首次使用，一键初始化
  python ezyrag.py init                 # 修改配置
  python ezyrag.py service              # 启动/停止服务
  python ezyrag.py db list              # 查看文档映射
  python ezyrag.py db add --all         # 添加所有本地文档
  python ezyrag.py db sync              # 同步本地和向量库
  python ezyrag.py build                # 增量构建知识库
  python ezyrag.py build --full         # 全量重建
  python ezyrag.py health               # 检查服务状态
"""
import os
import sys
import socket
import subprocess
from pathlib import Path

# Windows 终端编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================
#  工具函数
# ============================================================

def check_port(host: str, port: int) -> bool:
    """检查端口是否可连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def check_python() -> tuple:
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        return False, f"{version.major}.{version.minor}.{version.micro}"
    return True, f"{version.major}.{version.minor}.{version.micro}"


def check_uv() -> bool:
    """检查 uv 是否安装"""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_env() -> bool:
    """检查 .env 是否存在"""
    return (ROOT / "config" / ".env").exists()


def run_script(script: str, args: list = None):
    """运行 Python 脚本"""
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, cwd=ROOT)


def run_module(module: str, args: list = None):
    """运行 Python 模块"""
    cmd = [sys.executable, "-m", module]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, cwd=ROOT)


def pause():
    """暂停等待用户输入"""
    input("\n  按 Enter 继续...")


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: str, description: str):
    """打印步骤"""
    print(f"\n  Step {step}: {description}")
    print("  " + "-" * 40)


def print_ok(message: str):
    """打印成功信息"""
    print(f"  ✓ {message}")


def print_error(message: str):
    """打印错误信息"""
    print(f"  ✗ {message}")


def print_warn(message: str):
    """打印警告信息"""
    print(f"  ⚠ {message}")


def print_info(message: str):
    """打印信息"""
    print(f"  {message}")


# ============================================================
#  环境检查
# ============================================================

def check_environment() -> bool:
    """检查环境是否就绪"""
    print("\n  环境检查：")
    print("  " + "-" * 40)
    
    # 检查 Python
    ok, ver = check_python()
    if ok:
        print_ok(f"Python {ver}")
    else:
        print_error(f"Python {ver}（需要 >= 3.11）")
        print_info("请安装 Python 3.11+：https://www.python.org/downloads/")
        return False
    
    # 检查 uv
    if check_uv():
        print_ok("uv 已安装")
    else:
        print_error("uv 未安装")
        print_info("安装命令：powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
        return False
    
    # 检查 .env
    if check_env():
        print_ok("config/.env 已存在")
    else:
        print_warn("config/.env 不存在（将从模板创建）")
    
    print("  " + "-" * 40)
    return True


# ============================================================
#  quickstart 命令
# ============================================================

def cmd_quickstart():
    """快速开始向导"""
    print_header("Ezy-RAG Quick Start 向导")
    
    # Step 1: 环境检查
    print_step("1", "环境检查")
    ok = check_environment()
    if not ok:
        print("\n  环境检查未通过，请先解决上述问题。")
        return
    
    # Step 2: 安装依赖
    print_step("2", "安装依赖")
    
    # 检查 .venv 是否存在
    if not (ROOT / ".venv").exists():
        print_info("正在创建虚拟环境...")
        result = subprocess.run(["uv", "venv"], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"创建虚拟环境失败：{result.stderr}")
            return
        print_ok("虚拟环境已创建")
    
    print_info("正在安装依赖...")
    result = subprocess.run(["uv", "sync"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print_error(f"安装依赖失败：{result.stderr}")
        return
    print_ok("依赖已安装")
    
    # Step 3: 配置
    print_step("3", "配置")
    print_info("即将启动配置向导...")
    pause()
    run_script("cli/init.py")
    
    # Step 4: 添加本地文档（可选）
    print_step("4", "添加本地文档")
    
    docs_dir = ROOT / "data" / "docs"
    if docs_dir.exists():
        # 统计文档数量
        doc_count = 0
        for ext in [".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs"]:
            doc_count += len(list(docs_dir.glob(f"**/*{ext}")))
        
        if doc_count > 0:
            print_info(f"发现 {doc_count} 个本地文档")
            choice = input("  是否添加到向量库？(Y/n): ").strip().lower()
            if choice != 'n':
                print_info("正在添加文档...")
                run_script("cli/db_manage.py", ["add", "--all"])
            else:
                print_info("跳过添加文档")
        else:
            print_info("data/docs/ 目录为空，跳过添加文档")
    else:
        print_info("data/docs/ 目录不存在，跳过添加文档")
    
    # Step 5: 启动服务
    print_step("5", "启动服务")
    print_info("即将启动服务管理...")
    pause()
    run_script("cli/start_all.py")
    
    # 完成
    print_header("Quick Start 完成！")
    print("\n  下一步操作：")
    print_info("python ezyrag.py db list          # 查看文档映射")
    print_info("python ezyrag.py health           # 检查服务状态")
    print_info("python ezyrag.py service          # 管理服务")
    print_info("python ezyrag.py db add --all     # 添加更多文档")
    print("")


# ============================================================
#  init 命令
# ============================================================

def cmd_init():
    """配置管理"""
    print_header("配置管理")
    print_info("即将启动配置管理脚本...")
    pause()
    run_script("cli/init.py")


# ============================================================
#  service 命令
# ============================================================

def cmd_service():
    """服务管理"""
    print_header("服务管理")
    print_info("即将启动服务管理脚本...")
    pause()
    run_script("cli/start_all.py")


# ============================================================
#  db 命令
# ============================================================

def cmd_db(args):
    """数据库管理"""
    if not args:
        # 无参数，进入交互式菜单
        print_header("数据库管理")
        print_info("即将启动数据库管理脚本...")
        pause()
        run_script("cli/db_manage.py")
    else:
        # 有参数，转发命令
        print(f"\n  执行: python db_manage.py {' '.join(args)}")
        print("  " + "-" * 40)
        run_script("cli/db_manage.py", args)


# ============================================================
#  build 命令
# ============================================================

def cmd_build(args):
    """知识库构建"""
    if not args:
        # 无参数，显示提示
        print_header("知识库构建")
        print("\n  用法：")
        print_info("python ezyrag.py build              # 增量构建")
        print_info("python ezyrag.py build --full       # 全量重建")
        print_info("python ezyrag.py build -t chinese   # 指定切块模板")
        return
    
    print(f"\n  执行: python -m core.database {' '.join(args)}")
    print("  " + "-" * 40)
    run_module("core.database", args)


# ============================================================
#  health 命令
# ============================================================

def cmd_health():
    """健康检查"""
    print_header("Ezy-RAG 健康检查")
    
    # 从 .env 读取配置
    env_path = ROOT / "config" / ".env"
    env_config = {}
    
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_config[key.strip()] = value.strip()
    
    # 检查服务状态
    print("\n  服务状态：")
    print("  " + "-" * 50)
    
    # ChromaDB
    chroma_host = env_config.get("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(env_config.get("CHROMA_SERVER_PORT", "9898"))
    chroma_ok = check_port(chroma_host, chroma_port)
    print(f"  {'✓' if chroma_ok else '✗'} ChromaDB    : {'运行中' if chroma_ok else '未运行'} ({chroma_host}:{chroma_port})")
    
    # MCP
    mcp_host = env_config.get("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port = int(env_config.get("MCP_SERVER_PORT", "9766"))
    mcp_ok = check_port(mcp_host, mcp_port)
    print(f"  {'✓' if mcp_ok else '✗'} MCP         : {'运行中' if mcp_ok else '未运行'} ({mcp_host}:{mcp_port})")
    
    # Embedding
    embedding_mode = env_config.get("EMBEDDING_MODE", "cloud")
    if embedding_mode == "local":
        embedding_url = env_config.get("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        try:
            embedding_port = int(embedding_url.split(":")[-1].split("/")[0])
        except:
            embedding_port = 1234
        embedding_ok = check_port("127.0.0.1", embedding_port)
        print(f"  {'✓' if embedding_ok else '✗'} Embedding   : {'运行中' if embedding_ok else '未运行'} (本地模式, 端口 {embedding_port})")
    else:
        embedding_url = env_config.get("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
        api_key = env_config.get("EMBEDDING_CLOUD_API_KEY", "")
        try:
            domain = embedding_url.split("//")[1].split("/")[0]
        except:
            domain = "unknown"
        if api_key:
            print(f"  ✓ Embedding   : 已配置 (云端模式, {domain})")
        else:
            print(f"  ✗ Embedding   : 未配置 (云端模式, {domain})")
    
    # Rerank
    rerank_enabled = env_config.get("RERANK_ENABLED", "true").lower() == "true"
    if rerank_enabled:
        rerank_mode = env_config.get("RERANK_MODE", "local")
        if rerank_mode == "local":
            rerank_url = env_config.get("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
            try:
                rerank_port = int(rerank_url.split(":")[-1].split("/")[0])
            except:
                rerank_port = 5001
            rerank_ok = check_port("127.0.0.1", rerank_port)
            print(f"  {'✓' if rerank_ok else '✗'} Rerank      : {'运行中' if rerank_ok else '未运行'} (本地模式, 端口 {rerank_port})")
        else:
            rerank_url = env_config.get("RERANK_CLOUD_URL", "https://api.cohere.com/v1/rerank")
            api_key = env_config.get("RERANK_CLOUD_API_KEY", "")
            try:
                domain = rerank_url.split("//")[1].split("/")[0]
            except:
                domain = "unknown"
            if api_key:
                print(f"  ✓ Rerank      : 已配置 (云端模式, {domain})")
            else:
                print(f"  ✗ Rerank      : 未配置 (云端模式, {domain})")
    else:
        print(f"  - Rerank      : 未启用")
    
    # 数据库状态
    print("\n  数据库状态：")
    print("  " + "-" * 50)
    
    if chroma_ok:
        try:
            import chromadb
            from config.pointer import get_active_collection
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            
            collection_name = get_active_collection("default_collection")
            
            try:
                collection = client.get_collection(name=collection_name)
                count = collection.count()
                print_info(f"集合名      : {collection_name}")
                print_info(f"向量数量    : {count}")
                
                # 检查孤立记录
                result = collection.get(include=["metadatas"])
                if result and result["metadatas"]:
                    sources = set()
                    for meta in result["metadatas"]:
                        src = meta.get("source", "")
                        if src:
                            sources.add(src)
                    
                    orphan_count = 0
                    for src in sources:
                        for meta in result["metadatas"]:
                            if meta.get("source") == src:
                                source_type = meta.get("source_type", "local_file")
                                if source_type == "local_file" and not Path(src).exists():
                                    orphan_count += 1
                                break
                    
                    if orphan_count > 0:
                        print_warn(f"孤立记录  : {orphan_count} 个（本地文件已删除）")
                        print_info(f"清理命令  : python ezyrag.py db clean")
                    else:
                        print_info(f"孤立记录    : 0 个")
            except Exception as e:
                print_info(f"集合不存在  : {e}")
        except Exception as e:
            print_info(f"连接失败    : {e}")
    else:
        print_info("ChromaDB 未运行，无法获取数据库状态")
    
    print("\n" + "=" * 60)


# ============================================================
#  帮助信息
# ============================================================

def show_help():
    """显示帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Ezy-RAG V0.0.18 — 知识库系统                                ║
╚══════════════════════════════════════════════════════════════╝

用法：
  python ezyrag.py <command> [args...]

命令：
  quickstart          快速开始向导（首次使用）
  init                配置管理（交互式菜单）
  service             服务管理（交互式菜单）
  db <args>           数据库管理
  build [args]        知识库构建
  health              健康检查
  help                显示此帮助

数据库管理 (db)：
  python ezyrag.py db                 # 交互式菜单
  python ezyrag.py db list            # 查看文档映射
  python ezyrag.py db status          # 数据库状态
  python ezyrag.py db add --all       # 添加所有本地文档
  python ezyrag.py db add <file>      # 添加指定文件
  python ezyrag.py db add-web         # 添加网页内容
  python ezyrag.py db sync            # 同步本地和向量库
  python ezyrag.py db clean           # 清理孤立记录
  python ezyrag.py db rebuild         # 全量重建
  python ezyrag.py db delete <file>   # 删除向量记录
  python ezyrag.py db update --all    # 更新所有文档

知识库构建 (build)：
  python ezyrag.py build              # 增量构建
  python ezyrag.py build --full       # 全量重建
  python ezyrag.py build -t chinese   # 指定切块模板

首次使用：
  python ezyrag.py quickstart         # 一键初始化

常用工作流：
  1. python ezyrag.py quickstart      # 初始化配置
  2. python ezyrag.py db add --all    # 添加文档
  3. python ezyrag.py build           # 构建知识库
  4. python ezyrag.py health          # 检查状态
""")


# ============================================================
#  主入口
# ============================================================

def main():
    """主函数"""
    # 获取命令行参数
    args = sys.argv[1:]
    
    # 无参数，显示帮助
    if not args:
        show_help()
        return
    
    # 解析命令
    command = args[0].lower()
    remaining_args = args[1:]
    
    # 分发命令
    if command == "quickstart":
        cmd_quickstart()
    elif command == "init":
        cmd_init()
    elif command == "service":
        cmd_service()
    elif command == "db":
        cmd_db(remaining_args)
    elif command == "build":
        cmd_build(remaining_args)
    elif command == "health":
        cmd_health()
    elif command in ["help", "--help", "-h"]:
        show_help()
    else:
        print(f"\n  未知命令: {command}")
        print(f"  使用 'python ezyrag.py help' 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()

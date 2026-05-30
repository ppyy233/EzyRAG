# -*- coding: utf-8 -*-
"""
Ezy-RAG — 终端 UI 工具库
参考前端设计的简洁终端交互组件"""


def header(title: str, desc: str = ""):
    """打印页面标题"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    if desc:
        print(f"  {desc}")
    print("=" * 50)


def status_card(services: list):
    """打印服务状态卡片
    
    services: [{"name": "ChromaDB", "online": True, "info": ":9898"}, ...]
    """
    print("\n  服务状态:")
    print("  " + "-" * 46)
    for svc in services:
        icon = "[OK]" if svc.get("online") else ("[ -]" if svc.get("skip") else "[!!]")
        status = "Online" if svc.get("online") else ("N/A" if svc.get("skip") else "Offline")
        info = svc.get("info", "")
        print(f"  {icon} {svc['name']:<12} {status:<8} {info}")
    print("  " + "-" * 46)


def info_card(title: str, items: dict):
    """打印信息卡片
    
    items: {"key": "value", ...}
    """
    print(f"\n  {title}:")
    print("  " + "-" * 46)
    for key, value in items.items():
        print(f"  {key}: {value}")
    print("  " + "-" * 46)


def table(headers: list, rows: list, max_width: int = 80):
    """打印表格
    
    headers: ["列1", "列2"]
    rows: [["值1", "值2"], ...]
    """
    if not rows:
        print("\n  (空)")
        return
    
    # 计算列宽
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # 限制总宽度
    total = sum(widths) + 3 * (len(widths) - 1)
    if total > max_width:
        ratio = (max_width - 3 * (len(widths) - 1)) / sum(widths)
        widths = [max(8, int(w * ratio)) for w in widths]
    
    # 打印表头
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(f"\n  {header_line}")
    print("  " + "-" * len(header_line))
    
    # 打印行
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            s = str(cell)
            if len(s) > widths[i]:
                s = s[:widths[i]-3] + "..."
            cells.append(s.ljust(widths[i]))
        print(f"  {' | '.join(cells)}")


def log_ok(message: str):
    """成功日志"""
    print(f"  ✓ {message}")


def log_error(message: str):
    """错误日志"""
    print(f"  ✗ {message}")


def log_warn(message: str):
    """警告日志"""
    print(f"  ⚡ {message}")


def log_info(message: str):
    """信息日志"""
    print(f"  ℹ {message}")


def log_step(message: str):
    """步骤日志"""
    print(f"\n  ➤ {message}")


def confirm(message: str, default: bool = False) -> bool:
    """确认对话框"""
    hint = "Y/n" if default else "y/N"
    choice = input(f"\n  {message} ({hint}): ").strip().lower()
    if not choice:
        return default
    return choice in ("y", "yes", "是")


def menu(title: str, options: list) -> int:
    """菜单选择
    
    options: ["选项1", "选项2", ...]
    返回: 选择的索引 (1-based)，0 表示退出/返回
    """
    print(f"\n  {title}:")
    print("  " + "-" * 46)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  " + "-" * 46)
    
    while True:
        try:
            choice = input("  请选择: ").strip()
            if not choice:
                continue
            num = int(choice)
            if 1 <= num <= len(options):
                return num
            print(f"  请输入 1-{len(options)}")
        except ValueError:
            print("  请输入数字")


def menu_with_back(title: str, options: list) -> int:
    """带返回选项的菜单"""
    all_options = options + ["返回"]
    return menu(title, all_options)


def pause():
    """暂停等待用户输入"""
    input("\n  按 Enter 继续...")


def clear():
    """清屏"""
    import os
    os.system("cls" if os.name == "nt" else "clear")


def print_separator():
    """打印分隔线"""
    print("  " + "-" * 46)


def progress_bar(current: int, total: int, prefix: str = "", suffix: str = ""):
    """进度条
    
    使用 sys.stdout 确保在 Windows 终端中正常显示
    """
    import sys
    
    if total == 0:
        return
    
    percent = current / total
    bar_length = 30
    filled = int(bar_length * percent)
    bar = "=" * filled + "-" * (bar_length - filled)
    
    # 截断过长的 suffix
    max_suffix_len = 30
    if len(suffix) > max_suffix_len:
        suffix = suffix[:max_suffix_len-3] + "..."
    
    # 使用 sys.stdout.write 确保立即刷新
    sys.stdout.write(f"\r  {prefix} [{bar}] {current}/{total} {suffix}   ")
    sys.stdout.flush()
    
    if current == total:
        sys.stdout.write("\n")
        sys.stdout.flush()

def select_data_source(prompt: str = "选择数据源") -> str:
    """数据源选择交互
    
    Args:
        prompt: 提示信息
        
    Returns:
        "all" | "docs" | "web"
    """
    choice = menu(prompt, [
        "所有数据 (docs + web)",
        "仅本地文档 (docs)",
        "仅网页数据 (web)"
    ])
    return ["all", "docs", "web"][choice - 1]

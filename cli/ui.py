# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?缁堢 UI 宸ュ叿搴?鍙傝€冨墠绔璁＄殑绠€娲佺粓绔氦浜掔粍浠?"""


def header(title: str, desc: str = ""):
    """鎵撳嵃椤甸潰鏍囬"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    if desc:
        print(f"  {desc}")
    print("=" * 50)


def status_card(services: list):
    """鎵撳嵃鏈嶅姟鐘舵€佸崱鐗?    
    services: [{"name": "ChromaDB", "online": True, "info": ":9898"}, ...]
    """
    print("\n  鏈嶅姟鐘舵€?")
    print("  " + "-" * 46)
    for svc in services:
        icon = "[OK]" if svc.get("online") else ("[ -]" if svc.get("skip") else "[!!]")
        status = "Online" if svc.get("online") else ("N/A" if svc.get("skip") else "Offline")
        info = svc.get("info", "")
        print(f"  {icon} {svc['name']:<12} {status:<8} {info}")
    print("  " + "-" * 46)


def info_card(title: str, items: dict):
    """鎵撳嵃淇℃伅鍗＄墖
    
    items: {"key": "value", ...}
    """
    print(f"\n  {title}:")
    print("  " + "-" * 46)
    for key, value in items.items():
        print(f"  {key}: {value}")
    print("  " + "-" * 46)


def table(headers: list, rows: list, max_width: int = 80):
    """鎵撳嵃琛ㄦ牸
    
    headers: ["鍒?", "鍒?"]
    rows: [["鍊?", "鍊?"], ...]
    """
    if not rows:
        print("\n  (绌?")
        return
    
    # 璁＄畻鍒楀
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # 闄愬埗鎬诲搴?    total = sum(widths) + 3 * (len(widths) - 1)
    if total > max_width:
        ratio = (max_width - 3 * (len(widths) - 1)) / sum(widths)
        widths = [max(8, int(w * ratio)) for w in widths]
    
    # 鎵撳嵃琛ㄥご
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(f"\n  {header_line}")
    print("  " + "-" * len(header_line))
    
    # 鎵撳嵃琛?    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            s = str(cell)
            if len(s) > widths[i]:
                s = s[:widths[i]-3] + "..."
            cells.append(s.ljust(widths[i]))
        print(f"  {' | '.join(cells)}")


def log_ok(message: str):
    """鎴愬姛鏃ュ織"""
    print(f"  鉁?{message}")


def log_error(message: str):
    """閿欒鏃ュ織"""
    print(f"  鉁?{message}")


def log_warn(message: str):
    """璀﹀憡鏃ュ織"""
    print(f"  鈿?{message}")


def log_info(message: str):
    """淇℃伅鏃ュ織"""
    print(f"  鈩?{message}")


def log_step(message: str):
    """姝ラ鏃ュ織"""
    print(f"\n  鈫?{message}")


def confirm(message: str, default: bool = False) -> bool:
    """纭瀵硅瘽妗?""
    hint = "Y/n" if default else "y/N"
    choice = input(f"\n  {message} ({hint}): ").strip().lower()
    if not choice:
        return default
    return choice in ("y", "yes", "鏄?)


def menu(title: str, options: list) -> int:
    """鑿滃崟閫夋嫨
    
    options: ["閫夐」1", "閫夐」2", ...]
    杩斿洖: 閫夋嫨鐨勭储寮?(1-based)锛?琛ㄧず閫€鍑?杩斿洖
    """
    print(f"\n  {title}:")
    print("  " + "-" * 46)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  " + "-" * 46)
    
    while True:
        try:
            choice = input("  璇烽€夋嫨: ").strip()
            if not choice:
                continue
            num = int(choice)
            if 1 <= num <= len(options):
                return num
            print(f"  璇疯緭鍏?1-{len(options)}")
        except ValueError:
            print("  璇疯緭鍏ユ暟瀛?)


def menu_with_back(title: str, options: list) -> int:
    """甯﹁繑鍥為€夐」鐨勮彍鍗?""
    all_options = options + ["杩斿洖"]
    return menu(title, all_options)


def pause():
    """鏆傚仠绛夊緟鐢ㄦ埛杈撳叆"""
    input("\n  鎸?Enter 缁х画...")


def clear():
    """娓呭睆"""
    import os
    os.system("cls" if os.name == "nt" else "clear")


def print_separator():
    """鎵撳嵃鍒嗛殧绾?""
    print("  " + "-" * 46)


def progress_bar(current: int, total: int, prefix: str = "", suffix: str = ""):
    """杩涘害鏉?""
    if total == 0:
        return
    percent = current / total
    bar_length = 30
    filled = int(bar_length * percent)
    bar = "鈻? * filled + "鈻? * (bar_length - filled)
    print(f"\r  {prefix} [{bar}] {current}/{total} {suffix}", end="", flush=True)
    if current == total:
        print()  # 瀹屾垚鏃舵崲琛?

def select_data_source(prompt: str = "閫夋嫨鏁版嵁婧?) -> str:
    """鏁版嵁婧愰€夋嫨浜や簰
    
    Args:
        prompt: 鎻愮ず淇℃伅
        
    Returns:
        "all" | "docs" | "web"
    """
    choice = menu(prompt, [
        "鎵€鏈夋暟鎹?(docs + web)",
        "浠呮湰鍦版枃妗?(docs)",
        "浠呯綉椤垫暟鎹?(web)"
    ])
    return ["all", "docs", "web"][choice - 1]

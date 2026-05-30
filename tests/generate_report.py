# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 综合测试报告生成器
"""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

# 读取两个测试报告
report1_file = ROOT / "tests" / "test_report.json"
report2_file = ROOT / "tests" / "core_test_report.json"

with open(report1_file, "r", encoding="utf-8") as f:
    report1 = json.load(f)

with open(report2_file, "r", encoding="utf-8") as f:
    report2 = json.load(f)

# 合并结果
all_results = report1["results"] + report2["results"]
total = len(all_results)
passed = sum(1 for r in all_results if r["passed"])
failed = total - passed

# 生成报告
report = {
    "title": "Ezy-RAG V0.0.17 综合测试报告",
    "generated_at": datetime.now().isoformat(),
    "summary": {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{passed/total*100:.1f}%"
    },
    "test_suites": [
        {
            "name": "基础功能测试 (test_all.py)",
            "file": "test_report.json",
            "total": report1["total"],
            "passed": report1["passed"],
            "failed": report1["failed"]
        },
        {
            "name": "Core模块测试 (test_core.py)",
            "file": "core_test_report.json",
            "total": report2["total"],
            "passed": report2["passed"],
            "failed": report2["failed"]
        }
    ],
    "detailed_results": all_results
}

# 保存报告
output_file = ROOT / "tests" / "final_test_report.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# 打印摘要
print("=" * 70)
print("  Ezy-RAG V0.0.17 综合测试报告")
print("=" * 70)
print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print(f"\n  测试套件:")
for suite in report["test_suites"]:
    print(f"    - {suite['name']}: {suite['passed']}/{suite['total']} 通过")

print(f"\n  总计:")
print(f"    总测试数: {total}")
print(f"    通过: {passed}")
print(f"    失败: {failed}")
print(f"    通过率: {passed/total*100:.1f}%")

if failed > 0:
    print(f"\n  失败的测试:")
    for r in all_results:
        if not r["passed"]:
            print(f"    - {r['name']}: {r['details']}")

print("\n" + "=" * 70)
print(f"  报告已保存: {output_file}")
print("=" * 70)

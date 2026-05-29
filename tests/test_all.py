# -*- coding: utf-8 -*-
import sys
import io
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent

results = []

def log(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "details": details})
    msg = f"  [{status}] {name}"
    if details and not passed:
        msg += f" - {details}"
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def pr(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

pr("=" * 60)
pr("  Ezy-RAG Test Suite")
pr("=" * 60)

# Test 1: .env variables
print("\n--- Test 1: .env variables ---")
env_file = ROOT / "config" / ".env"
with open(env_file, "r", encoding="utf-8") as f:
    content = f.read()
log("EMBEDDING_MODE exists", "EMBEDDING_MODE=" in content)
log("EMBEDDING_LOCAL_MODEL_PATH exists", "EMBEDDING_LOCAL_MODEL_PATH=" in content)
log("EMBEDDING_LOCAL_DIM exists", "EMBEDDING_LOCAL_DIM=" in content)
log("RERANK_MODE exists", "RERANK_MODE=" in content)
log("RERANK_ENABLED exists", "RERANK_ENABLED=" in content)
log("RERANK_LOCAL_MODEL_PATH exists", "RERANK_LOCAL_MODEL_PATH=" in content)

# Test 2: Path conversion
print("\n--- Test 2: Path conversion ---")
from dotenv import load_dotenv
load_dotenv(env_file)

model_path = os.getenv("EMBEDDING_LOCAL_MODEL_PATH", "")
model_dir = Path(model_path)
if not model_dir.is_absolute():
    model_dir = ROOT / model_dir
log("Embedding path converts to absolute", model_dir.is_absolute(), str(model_dir))
log("Embedding model dir exists", model_dir.exists(), str(model_dir))

rerank_path = os.getenv("RERANK_LOCAL_MODEL_PATH", "")
rerank_dir = Path(rerank_path)
if not rerank_dir.is_absolute():
    rerank_dir = ROOT / rerank_dir
log("Rerank path converts to absolute", rerank_dir.is_absolute(), str(rerank_dir))
log("Rerank model dir exists", rerank_dir.exists(), str(rerank_dir))

# Test 3: config/settings functions
print("\n--- Test 3: config/settings functions ---")
from config.settings import (
    get_embedding_mode, get_embedding_config,
    get_rerank_mode, get_rerank_enabled, get_rerank_config,
    get_collection_name, get_chunk_config, get_retrieval_config
)
emb_mode = get_embedding_mode()
log("get_embedding_mode()", emb_mode in ["local", "cloud"], f"mode={emb_mode}")

emb_cfg = get_embedding_config()
log("get_embedding_config()", "mode" in emb_cfg, f"keys={list(emb_cfg.keys())}")

rerank_mode = get_rerank_mode()
log("get_rerank_mode()", rerank_mode in ["local", "cloud"], f"mode={rerank_mode}")

rerank_enabled = get_rerank_enabled()
log("get_rerank_enabled()", isinstance(rerank_enabled, bool), f"enabled={rerank_enabled}")

rerank_cfg = get_rerank_config()
log("get_rerank_config()", "mode" in rerank_cfg, f"keys={list(rerank_cfg.keys())}")

collection = get_collection_name()
log("get_collection_name()", bool(collection), f"name={collection}")

chunk_cfg = get_chunk_config()
log("get_chunk_config()", "chunk_size" in chunk_cfg, f"chunk_size={chunk_cfg.get('chunk_size')}")

retrieval_cfg = get_retrieval_config()
log("get_retrieval_config()", "k" in retrieval_cfg, f"k={retrieval_cfg.get('k')}, fetch_k={retrieval_cfg.get('fetch_k')}")

# Test 4: start_all imports
print("\n--- Test 4: start_all module ---")
from start_all import OUR_PORTS, get_pid_by_port, cleanup_zombie_processes
log("OUR_PORTS loaded", True, str(OUR_PORTS))
log("get_pid_by_port callable", callable(get_pid_by_port))
log("cleanup_zombie_processes callable", callable(cleanup_zombie_processes))

# Test get_pid_by_port
pid = get_pid_by_port(99999)
log("get_pid_by_port for unused port", pid == "-", f"pid={pid}")

# Test 5: db_manage imports
print("\n--- Test 5: db_manage module ---")
from db_manage import get_local_documents
docs = get_local_documents()
log("get_local_documents()", True, f"{len(docs)} files")

# Test 6: local modules
print("\n--- Test 6: local modules ---")
from local.embedding import load_model as emb_load
from local.rerank import load_model as rerank_load
log("local.embedding.load_model exists", callable(emb_load))
log("local.rerank.load_model exists", callable(rerank_load))

# Test 7: core modules
print("\n--- Test 7: core modules ---")
from core.scheduler import get_scheduler
from core.repository import DocumentRepository
log("get_scheduler exists", callable(get_scheduler))
log("DocumentRepository exists", callable(DocumentRepository))

# Test 8: config.json
print("\n--- Test 8: config.json ---")
config_file = ROOT / "config" / "config.json"
with open(config_file, "r", encoding="utf-8") as f:
    cfg = json.load(f)
log("retrieval.k exists", "k" in cfg.get("retrieval", {}), f"k={cfg.get('retrieval', {}).get('k')}")
log("retrieval.fetch_k exists", "fetch_k" in cfg.get("retrieval", {}), f"fetch_k={cfg.get('retrieval', {}).get('fetch_k')}")
log("chunk.templates exists", "templates" in cfg.get("chunk", {}))

# Summary
print("\n" + "=" * 60)
passed = sum(1 for r in results if r["passed"])
total = len(results)
failed = total - passed
print(f"  Total: {total}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Pass rate: {passed/total*100:.1f}%")

if failed > 0:
    print("\n  Failed tests:")
    for r in results:
        if not r["passed"]:
            print(f"    - {r['name']}: {r['details']}")
print("=" * 60)

# Save report
report = {
    "total": total,
    "passed": passed,
    "failed": failed,
    "results": results
}
report_file = ROOT / "tests" / "test_report.json"
with open(report_file, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\nReport saved: {report_file}")

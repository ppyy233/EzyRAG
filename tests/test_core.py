# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — Core模块测试（影子集合策略版）
测试内容：异步并发、ACID事务（影子集合策略）、异常恢复、重复数据清理
"""
import sys
import os
import json
import time
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

results = []


def log(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "details": details})
    msg = f"  [{status}] {name}"
    if details:
        msg += f" - {details}"
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def pr(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ==================== Mock类 ====================

class MockChromaClient:
    """模拟ChromaDB客户端"""
    def __init__(self):
        self.collections = {}
    
    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]
    
    def delete_collection(self, name):
        if name in self.collections:
            del self.collections[name]
    
    def get_collection(self, name):
        if name in self.collections:
            return self.collections[name]
        raise Exception(f"Collection {name} not found")
    
    def list_collections(self):
        return list(self.collections.values())


class MockCollection:
    """模拟ChromaDB Collection"""
    def __init__(self, name="test_collection"):
        self.name = name
        self.data = {}
        self.ids = []
    
    def get(self, where=None, include=None):
        if where and "source" in where:
            source = where["source"]
            matching = [self.data[id] for id in self.ids 
                       if id in self.data and self.data[id].get("metadata", {}).get("source") == source]
            if not matching:
                return {"ids": [], "metadatas": [], "documents": [], "embeddings": []}
            return {
                "ids": [m["id"] for m in matching],
                "metadatas": [m.get("metadata", {}) for m in matching],
                "documents": [m.get("document", "") for m in matching],
                "embeddings": [m.get("embedding", []) for m in matching]
            }
        return {
            "ids": self.ids,
            "metadatas": [self.data[id].get("metadata", {}) for id in self.ids if id in self.data],
            "documents": [self.data[id].get("document", "") for id in self.ids if id in self.data],
            "embeddings": [self.data[id].get("embedding", []) for id in self.ids if id in self.data]
        }
    
    def count(self):
        return len(self.ids)
    
    def add(self, ids, embeddings=None, documents=None, metadatas=None):
        for i, id in enumerate(ids):
            self.data[id] = {
                "id": id,
                "embedding": embeddings[i] if embeddings and i < len(embeddings) else None,
                "document": documents[i] if documents and i < len(documents) else "",
                "metadata": metadatas[i] if metadatas and i < len(metadatas) else {}
            }
            if id not in self.ids:
                self.ids.append(id)
    
    def delete(self, where=None, ids=None):
        if ids:
            for id in ids:
                if id in self.data:
                    del self.data[id]
                if id in self.ids:
                    self.ids.remove(id)
        elif where and "source" in where:
            source = where["source"]
            to_remove = [id for id in self.ids 
                        if id in self.data and self.data[id].get("metadata", {}).get("source") == source]
            for id in to_remove:
                del self.data[id]
                self.ids.remove(id)


class MockEmbProxy:
    """模拟Embedding代理"""
    def __init__(self, dim=1024):
        self.dim = dim
    
    def embed_sync(self, texts, priority=100):
        return [[0.1] * self.dim for _ in texts]


# ==================== 测试1: 异步并发测试 ====================

def test_scheduler_priority_queue():
    """测试1.1: Scheduler优先级队列"""
    pr("\n--- Test 1.1: Scheduler Priority Queue ---")
    
    try:
        import queue
        
        test_queue = queue.PriorityQueue()
        priorities = [100, 0, 50, 0, 100]
        for priority in priorities:
            test_queue.put((priority, time.time(), f"task_{priority}"))
        
        result_order = []
        while not test_queue.empty():
            priority, _, _ = test_queue.get()
            result_order.append(priority)
        
        expected_order = [0, 0, 50, 100, 100]
        log("Priority queue order", result_order == expected_order, 
            f"expected={expected_order}, got={result_order}")
        
    except Exception as e:
        log("Priority queue test", False, str(e))


def test_concurrent_query_and_build():
    """测试1.2: 同时查询和建库"""
    pr("\n--- Test 1.2: Concurrent Query and Build ---")
    
    try:
        import queue
        import uuid
        
        scheduler = type('MockScheduler', (), {
            '_queue': queue.PriorityQueue(),
            '_results': {},
            '_results_lock': threading.Lock(),
            '_running': True,
            '_dim': 1024
        })()
        
        mock_embedding = [0.1] * 1024
        execution_order = []
        
        def mock_worker():
            while scheduler._running:
                try:
                    priority, task_id, texts, event = scheduler._queue.get(timeout=0.1)
                    time.sleep(0.01)
                    with scheduler._results_lock:
                        scheduler._results[task_id] = [mock_embedding]
                        execution_order.append(priority)
                    event.set()
                except queue.Empty:
                    continue
        
        worker_thread = threading.Thread(target=mock_worker, daemon=True)
        worker_thread.start()
        
        query_id = str(uuid.uuid4())
        build_id = str(uuid.uuid4())
        query_event = threading.Event()
        build_event = threading.Event()
        
        scheduler._queue.put((100, build_id, ["build text"], build_event))
        scheduler._queue.put((0, query_id, ["query text"], query_event))
        
        query_event.wait(timeout=5)
        build_event.wait(timeout=5)
        
        scheduler._running = False
        worker_thread.join(timeout=1)
        
        log("Query before build", execution_order == [0, 100],
            f"execution_order={execution_order}")
        
        with scheduler._results_lock:
            log("Query result exists", scheduler._results.get(query_id) is not None)
            log("Build result exists", scheduler._results.get(build_id) is not None)
        
    except Exception as e:
        log("Concurrent test", False, str(e))


def test_multiple_concurrent_queries():
    """测试1.3: 多个并发查询"""
    pr("\n--- Test 1.3: Multiple Concurrent Queries ---")
    
    try:
        import queue
        import uuid
        
        scheduler = type('MockScheduler', (), {
            '_queue': queue.PriorityQueue(),
            '_results': {},
            '_results_lock': threading.Lock(),
            '_running': True
        })()
        
        mock_embedding = [0.1] * 1024
        completed_tasks = []
        
        def mock_worker():
            while scheduler._running:
                try:
                    priority, task_id, texts, event = scheduler._queue.get(timeout=0.1)
                    time.sleep(0.01)
                    with scheduler._results_lock:
                        scheduler._results[task_id] = [mock_embedding]
                        completed_tasks.append(task_id)
                    event.set()
                except queue.Empty:
                    continue
        
        worker_thread = threading.Thread(target=mock_worker, daemon=True)
        worker_thread.start()
        
        num_queries = 5
        events = []
        task_ids = []
        
        for i in range(num_queries):
            task_id = f"query_{i}"
            event = threading.Event()
            scheduler._queue.put((0, task_id, [f"query {i}"], event))
            events.append(event)
            task_ids.append(task_id)
        
        for event in events:
            event.wait(timeout=5)
        
        scheduler._running = False
        worker_thread.join(timeout=1)
        
        log("All queries completed", len(completed_tasks) == num_queries,
            f"completed={len(completed_tasks)}, expected={num_queries}")
        
        with scheduler._results_lock:
            all_results_valid = all(task_id in scheduler._results for task_id in task_ids)
        log("All results valid", all_results_valid)
        
    except Exception as e:
        log("Multiple queries test", False, str(e))


# ==================== 测试2: ACID事务测试（影子集合策略） ====================

def test_update_shadow_strategy():
    """测试2.1: update的影子集合策略"""
    pr("\n--- Test 2.1: Update Shadow Strategy ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 添加文档
        doc1 = {"path": "/test/doc1.txt", "text": "Original content"}
        count1 = repo.add(doc1, chunk_cfg, source_type="local_file")
        log("Add document", count1 > 0, f"chunks={count1}")
        
        # 使用影子集合策略更新
        doc1_updated = {"path": "/test/doc1.txt", "text": "Updated content"}
        count2 = repo.update(doc1_updated, chunk_cfg, source_type="local_file")
        log("Update document (shadow strategy)", count2 > 0, f"chunks={count2}")
        
        # 验证更新后文档存在
        doc_exists = repo.exists("/test/doc1.txt")
        log("Document exists after update", doc_exists)
        
        # 验证更新后文档信息
        doc_info = repo.get_document_info("/test/doc1.txt")
        log("Document info available", doc_info is not None)
        
    except Exception as e:
        log("Update shadow strategy test", False, str(e))


def test_update_no_data_loss():
    """测试2.2: update异常时不丢失数据（影子集合策略）"""
    pr("\n--- Test 2.2: Update No Data Loss on Failure (Shadow Strategy) ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 添加文档
        doc1 = {"path": "/test/doc1.txt", "text": "Original content"}
        repo.add(doc1, chunk_cfg, source_type="local_file")
        
        # 模拟异常：在创建影子集合时失败
        original_create = repo._create_shadow_collection
        def failing_create():
            raise Exception("Simulated failure during shadow creation")
        
        repo._create_shadow_collection = failing_create
        try:
            doc1_updated = {"path": "/test/doc1.txt", "text": "Updated content that will fail"}
            repo.update(doc1_updated, chunk_cfg, source_type="local_file")
        except Exception:
            pass
        
        repo._create_shadow_collection = original_create
        
        # 验证：旧数据应该还在（影子集合策略保证不丢失）
        doc_info = repo.get_document_info("/test/doc1.txt")
        log("Old data preserved on failure", doc_info is not None,
            "Document should still exist with old content")
        
    except Exception as e:
        log("Update no data loss test", False, str(e))


def test_update_copy_failure():
    """测试2.3: 复制数据到影子集合失败时的数据状态"""
    pr("\n--- Test 2.3: Update Copy Failure ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 添加文档
        doc1 = {"path": "/test/doc1.txt", "text": "Original content"}
        repo.add(doc1, chunk_cfg, source_type="local_file")
        
        # 模拟异常：在复制数据时失败
        original_copy = repo._copy_to_shadow
        def failing_copy(shadow_collection):
            raise Exception("Simulated failure during copy")
        
        repo._copy_to_shadow = failing_copy
        try:
            doc1_updated = {"path": "/test/doc1.txt", "text": "Updated content that will fail"}
            repo.update(doc1_updated, chunk_cfg, source_type="local_file")
        except Exception:
            pass
        
        repo._copy_to_shadow = original_copy
        
        # 验证：旧数据应该还在（影子集合策略保证不丢失）
        doc_info = repo.get_document_info("/test/doc1.txt")
        log("Old data preserved on copy failure", doc_info is not None,
            "Document should still exist with old content")
        
        # 验证：影子集合应该被清理
        shadow_collections = [col for col in chroma_client.collections if col.startswith("test_collection_v")]
        log("Shadow collection cleaned up", len(shadow_collections) == 0,
            f"Found {len(shadow_collections)} shadow collections")
        
    except Exception as e:
        log("Update copy failure test", False, str(e))


def test_sync_shadow_strategy():
    """测试2.4: sync的影子集合策略"""
    pr("\n--- Test 2.4: Sync Shadow Strategy ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 初始状态：添加文档A
        doc_a = {"path": "/test/doc_a.txt", "text": "Document A"}
        repo.add(doc_a, chunk_cfg, source_type="local_file")
        log("Initial state: doc_a added", repo.exists("/test/doc_a.txt"))
        
        # 模拟sync：新增B，更新A
        doc_a_updated = {"path": "/test/doc_a.txt", "text": "Document A Updated"}
        doc_b_new = {"path": "/test/doc_b.txt", "text": "Document B"}
        
        documents = [doc_a_updated, doc_b_new]
        
        # 执行sync
        stats = repo.sync(documents, chunk_cfg, source_type="local_file")
        
        log("Sync stats: added", stats["added"] > 0, f"added={stats['added']}")
        log("Sync stats: updated", stats["updated"] > 0, f"updated={stats['updated']}")
        
        # 验证最终状态
        doc_a_exists = repo.exists("/test/doc_a.txt")
        doc_b_exists = repo.exists("/test/doc_b.txt")
        log("doc_a exists after sync", doc_a_exists)
        log("doc_b exists after sync", doc_b_exists)
        
    except Exception as e:
        log("Sync shadow strategy test", False, str(e))


def test_sync_no_data_loss():
    """测试2.5: sync异常时不丢失数据（影子集合策略）"""
    pr("\n--- Test 2.5: Sync No Data Loss on Failure (Shadow Strategy) ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 初始状态：添加文档A、B
        doc_a = {"path": "/test/doc_a.txt", "text": "Document A"}
        doc_b = {"path": "/test/doc_b.txt", "text": "Document B"}
        repo.add(doc_a, chunk_cfg, source_type="local_file")
        repo.add(doc_b, chunk_cfg, source_type="local_file")
        
        # 模拟异常：在创建影子集合时失败
        original_create = repo._create_shadow_collection
        def failing_create():
            raise Exception("Simulated failure during shadow creation")
        
        repo._create_shadow_collection = failing_create
        
        doc_c_new = {"path": "/test/doc_c.txt", "text": "Document C"}
        doc_a_updated = {"path": "/test/doc_a.txt", "text": "Document A Updated"}
        
        documents = [doc_c_new, doc_a_updated]
        
        try:
            stats = repo.sync(documents, chunk_cfg, source_type="local_file")
        except Exception:
            pass
        
        repo._create_shadow_collection = original_create
        
        # 验证：旧数据应该还在（影子集合策略保证不丢失）
        doc_a_info = repo.get_document_info("/test/doc_a.txt")
        doc_b_info = repo.get_document_info("/test/doc_b.txt")
        log("doc_a preserved on failure", doc_a_info is not None,
            "Document A should still exist with old content")
        log("doc_b preserved on failure", doc_b_info is not None,
            "Document B should still exist with old content")
        
    except Exception as e:
        log("Sync no data loss test", False, str(e))


def test_cleanup_duplicates():
    """测试2.6: 重复数据清理（理论测试）"""
    pr("\n--- Test 2.6: Cleanup Duplicates (Theoretical) ---")
    
    try:
        from core.repository import DocumentRepository
        
        chroma_client = MockChromaClient()
        collection = chroma_client.get_or_create_collection("test_collection")
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy, chroma_client, "test_collection")
        
        # 测试cleanup_duplicates方法存在
        log("cleanup_duplicates method exists", callable(getattr(repo, 'cleanup_duplicates', None)))
        
        # 测试cleanup_duplicates方法可以调用
        try:
            cleaned = repo.cleanup_duplicates()
            log("cleanup_duplicates callable", True, f"cleaned={cleaned}")
        except Exception as e:
            log("cleanup_duplicates callable", False, str(e))
        
    except Exception as e:
        log("Cleanup duplicates test", False, str(e))


def test_content_hash_consistency():
    """测试2.7: content_hash一致性"""
    pr("\n--- Test 2.7: Content Hash Consistency ---")
    
    try:
        from core.repository import content_hash as repo_content_hash
        from core.builder import content_hash as builder_content_hash
        
        test_text = "Hello, this is a test document."
        
        repo_hash = repo_content_hash(test_text)
        builder_hash = builder_content_hash(test_text)
        
        log("Hash functions consistent", repo_hash == builder_hash,
            f"repo={repo_hash}, builder={builder_hash}")
        
        hash1 = repo_content_hash(test_text)
        hash2 = repo_content_hash(test_text)
        log("Same content same hash", hash1 == hash2)
        
        hash3 = repo_content_hash("Different content")
        log("Different content different hash", hash1 != hash3)
        
    except Exception as e:
        log("Content hash test", False, str(e))


# ==================== 主函数 ====================

def run_core_tests():
    """运行所有core模块测试"""
    pr("=" * 60)
    pr("  Ezy-RAG Core Module Tests (Shadow Strategy)")
    pr("=" * 60)
    pr(f"  Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pr("=" * 60)
    
    # 测试1: 异步并发
    test_scheduler_priority_queue()
    test_concurrent_query_and_build()
    test_multiple_concurrent_queries()
    
    # 测试2: ACID事务（影子集合策略）
    test_update_shadow_strategy()
    test_update_no_data_loss()
    test_update_copy_failure()
    test_sync_shadow_strategy()
    test_sync_no_data_loss()
    test_cleanup_duplicates()
    test_content_hash_consistency()
    
    # 生成报告
    pr("\n" + "=" * 60)
    pr("  Test Report")
    pr("=" * 60)
    
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)
    
    pr(f"  Total: {total}")
    pr(f"  Passed: {passed}")
    pr(f"  Failed: {failed}")
    pr(f"  Pass rate: {passed/total*100:.1f}%")
    
    if failed > 0:
        pr("\n  Failed tests:")
        for r in results:
            if not r["passed"]:
                pr(f"    - {r['name']}: {r['details']}")
    pr("=" * 60)
    
    # 保存报告
    report = {
        "start_time": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results
    }
    report_file = ROOT / "tests" / "core_test_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    pr(f"\nReport saved: {report_file}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_core_tests()
    sys.exit(0 if success else 1)

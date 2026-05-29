# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — Core模块测试
测试内容：异步并发、ACID事务、异常恢复
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


# ==================== 测试1: 异步并发测试 ====================

def test_scheduler_priority_queue():
    """测试1.1: Scheduler优先级队列"""
    pr("\n--- Test 1.1: Scheduler Priority Queue ---")
    
    try:
        import queue
        
        # 创建模拟队列（带优先级的元组）
        test_queue = queue.PriorityQueue()
        
        # 添加不同优先级的任务（使用可比较的元组）
        priorities = [100, 0, 50, 0, 100]
        for priority in priorities:
            # 使用(priority, counter)作为比较键，避免比较Event对象
            test_queue.put((priority, time.time(), f"task_{priority}"))
        
        # 验证队列顺序（优先级小的先出）
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
        from core.scheduler import TaskScheduler
        import queue
        import uuid
        
        # 创建模拟调度器（不实际调用embedding）
        scheduler = TaskScheduler.__new__(TaskScheduler)
        scheduler._queue = queue.PriorityQueue()
        scheduler._results = {}
        scheduler._results_lock = threading.Lock()
        scheduler._running = True
        scheduler._dim = 1024
        
        # 模拟embedding结果
        mock_embedding = [0.1] * 1024
        
        results_captured = {"query": None, "build": None}
        execution_order = []
        
        def mock_worker():
            """模拟worker，按优先级处理任务"""
            while scheduler._running:
                try:
                    priority, task_id, texts, event = scheduler._queue.get(timeout=0.1)
                    # 模拟处理时间
                    time.sleep(0.01)
                    with scheduler._results_lock:
                        scheduler._results[task_id] = [mock_embedding]
                        execution_order.append(priority)
                    event.set()
                except queue.Empty:
                    continue
        
        # 启动worker
        worker_thread = threading.Thread(target=mock_worker, daemon=True)
        worker_thread.start()
        
        # 同时提交查询和建库任务
        query_id = str(uuid.uuid4())
        build_id = str(uuid.uuid4())
        
        query_event = threading.Event()
        build_event = threading.Event()
        
        # 先提交建库任务（priority=100）
        scheduler._queue.put((100, build_id, ["build text"], build_event))
        
        # 立即提交查询任务（priority=0）
        scheduler._queue.put((0, query_id, ["query text"], query_event))
        
        # 等待两个任务完成
        query_event.wait(timeout=5)
        build_event.wait(timeout=5)
        
        # 停止worker
        scheduler._running = False
        worker_thread.join(timeout=1)
        
        # 验证查询先于建库执行
        log("Query before build", execution_order == [0, 100],
            f"execution_order={execution_order}")
        
        # 验证结果正确
        with scheduler._results_lock:
            query_result = scheduler._results.get(query_id)
            build_result = scheduler._results.get(build_id)
        
        log("Query result exists", query_result is not None)
        log("Build result exists", build_result is not None)
        
    except Exception as e:
        log("Concurrent test", False, str(e))


def test_multiple_concurrent_queries():
    """测试1.3: 多个并发查询"""
    pr("\n--- Test 1.3: Multiple Concurrent Queries ---")
    
    try:
        from core.scheduler import TaskScheduler
        import queue
        import uuid
        
        scheduler = TaskScheduler.__new__(TaskScheduler)
        scheduler._queue = queue.PriorityQueue()
        scheduler._results = {}
        scheduler._results_lock = threading.Lock()
        scheduler._running = True
        scheduler._dim = 1024
        
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
        
        # 同时提交5个查询任务
        num_queries = 5
        events = []
        task_ids = []
        
        for i in range(num_queries):
            task_id = f"query_{i}"
            event = threading.Event()
            scheduler._queue.put((0, task_id, [f"query {i}"], event))
            events.append(event)
            task_ids.append(task_id)
        
        # 等待所有任务完成
        for event in events:
            event.wait(timeout=5)
        
        scheduler._running = False
        worker_thread.join(timeout=1)
        
        # 验证所有查询都完成
        log("All queries completed", len(completed_tasks) == num_queries,
            f"completed={len(completed_tasks)}, expected={num_queries}")
        
        # 验证所有结果都正确
        all_results_valid = True
        with scheduler._results_lock:
            for task_id in task_ids:
                if task_id not in scheduler._results:
                    all_results_valid = False
                    break
        
        log("All results valid", all_results_valid)
        
    except Exception as e:
        log("Multiple queries test", False, str(e))


# ==================== 测试2: ACID事务测试 ====================

def test_update_atomicity():
    """测试2.1: update操作原子性"""
    pr("\n--- Test 2.1: Update Atomicity ---")
    
    try:
        from core.repository import DocumentRepository, content_hash, chunk_single_document
        
        # 创建模拟collection
        class MockCollection:
            def __init__(self):
                self.data = {}
                self.ids = []
            
            def get(self, where=None, include=None):
                if where and "source" in where:
                    source = where["source"]
                    matching = [self.data[id] for id in self.ids if self.data[id].get("metadata", {}).get("source") == source]
                    if not matching:
                        return {"ids": [], "metadatas": [], "documents": []}
                    return {
                        "ids": [m["id"] for m in matching],
                        "metadatas": [m.get("metadata", {}) for m in matching],
                        "documents": [m.get("document", "") for m in matching]
                    }
                return {"ids": self.ids, "metadatas": [m.get("metadata", {}) for m in [self.data[id] for id in self.ids]], "documents": [m.get("document", "") for m in [self.data[id] for id in self.ids]]}
            
            def count(self):
                return len(self.ids)
            
            def add(self, ids, embeddings, documents, metadatas):
                for i, id in enumerate(ids):
                    self.data[id] = {
                        "id": id,
                        "embedding": embeddings[i] if i < len(embeddings) else None,
                        "document": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {}
                    }
                    self.ids.append(id)
            
            def delete(self, where=None):
                if where and "source" in where:
                    source = where["source"]
                    self.ids = [id for id in self.ids if self.data[id].get("metadata", {}).get("source") != source]
        
        # 创建模拟embedding代理
        class MockEmbProxy:
            def embed_sync(self, texts, priority=100):
                return [[0.1] * 1024 for _ in texts]
        
        collection = MockCollection()
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy)
        
        # 测试1: 正常update
        doc1 = {"path": "/test/doc1.txt", "text": "Original content"}
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 添加文档
        count1 = repo.add(doc1, chunk_cfg, source_type="local_file")
        log("Add document", count1 > 0, f"chunks={count1}")
        
        # 更新文档
        doc1_updated = {"path": "/test/doc1.txt", "text": "Updated content"}
        count2 = repo.update(doc1_updated, chunk_cfg, source_type="local_file")
        log("Update document", count2 > 0, f"chunks={count2}")
        
        # 验证更新后内容
        doc_info = repo.get_document_info("/test/doc1.txt")
        log("Document updated correctly", doc_info is not None)
        
        # 测试2: 模拟update失败（删除后添加前）
        doc2 = {"path": "/test/doc2.txt", "text": "Content to fail"}
        repo.add(doc2, chunk_cfg, source_type="local_file")
        
        # 模拟异常：在delete后、add前
        original_add = repo.add
        def failing_add(doc, chunk_cfg, source_type="local_file"):
            raise Exception("Simulated failure during add")
        
        repo.add = failing_add
        try:
            repo.update(doc2, chunk_cfg, source_type="local_file")
        except Exception:
            pass
        
        repo.add = original_add
        
        # 验证：文档应该不存在（数据丢失）
        doc_info2 = repo.get_document_info("/test/doc2.txt")
        log("Data loss on update failure", doc_info2 is None,
            "Document should not exist after failed update (data loss)")
        
    except Exception as e:
        log("Update atomicity test", False, str(e))


def test_sync_consistency():
    """测试2.2: sync操作一致性"""
    pr("\n--- Test 2.2: Sync Consistency ---")
    
    try:
        from core.repository import DocumentRepository
        
        class MockCollection:
            def __init__(self):
                self.data = {}
                self.ids = []
            
            def get(self, where=None, include=None):
                if where and "source" in where:
                    source = where["source"]
                    matching = [self.data[id] for id in self.ids if self.data[id].get("metadata", {}).get("source") == source]
                    if not matching:
                        return {"ids": [], "metadatas": [], "documents": []}
                    return {
                        "ids": [m["id"] for m in matching],
                        "metadatas": [m.get("metadata", {}) for m in matching],
                        "documents": [m.get("document", "") for m in matching]
                    }
                return {"ids": self.ids, "metadatas": [m.get("metadata", {}) for m in [self.data[id] for id in self.ids]], "documents": [m.get("document", "") for m in [self.data[id] for id in self.ids]]}
            
            def count(self):
                return len(self.ids)
            
            def add(self, ids, embeddings, documents, metadatas):
                for i, id in enumerate(ids):
                    self.data[id] = {
                        "id": id,
                        "embedding": embeddings[i] if i < len(embeddings) else None,
                        "document": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {}
                    }
                    self.ids.append(id)
            
            def delete(self, where=None):
                if where and "source" in where:
                    source = where["source"]
                    self.ids = [id for id in self.ids if self.data[id].get("metadata", {}).get("source") != source]
        
        class MockEmbProxy:
            def embed_sync(self, texts, priority=100):
                return [[0.1] * 1024 for _ in texts]
        
        collection = MockCollection()
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy)
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 初始状态：添加文档A
        doc_a = {"path": "/test/doc_a.txt", "text": "Document A"}
        repo.add(doc_a, chunk_cfg, source_type="local_file")
        log("Initial state: doc_a added", repo.exists("/test/doc_a.txt"))
        
        # 模拟sync：新增B，更新A，删除不存在的
        doc_a_updated = {"path": "/test/doc_a.txt", "text": "Document A Updated"}
        doc_b_new = {"path": "/test/doc_b.txt", "text": "Document B"}
        
        documents = [doc_a_updated, doc_b_new]
        
        # 执行sync
        stats = repo.sync(documents, chunk_cfg, source_type="local_file")
        
        log("Sync stats: added", stats["added"] > 0, f"added={stats['added']}")
        log("Sync stats: updated", stats["updated"] > 0, f"updated={stats['updated']}")
        
        # 验证最终状态
        log("doc_a exists after sync", repo.exists("/test/doc_a.txt"))
        log("doc_b exists after sync", repo.exists("/test/doc_b.txt"))
        
    except Exception as e:
        log("Sync consistency test", False, str(e))


def test_build_full_recovery():
    """测试2.3: 全量重建恢复"""
    pr("\n--- Test 2.3: Build Full Recovery ---")
    
    try:
        from core.builder import build_full, get_or_create_collection, split_text, get_active_collection
        from core.repository import DocumentRepository
        
        class MockChromaClient:
            def __init__(self):
                self.collections = {}
            
            def get_or_create_collection(self, name, metadata=None):
                if name not in self.collections:
                    self.collections[name] = MockCollection()
                return self.collections[name]
            
            def delete_collection(self, name):
                if name in self.collections:
                    del self.collections[name]
            
            def get_collection(self, name):
                if name in self.collections:
                    return self.collections[name]
                raise Exception(f"Collection {name} not found")
        
        class MockCollection:
            def __init__(self):
                self.data = {}
                self.ids = []
                self.name = "test_collection"
            
            def get(self, where=None, include=None):
                return {"ids": self.ids, "metadatas": [m.get("metadata", {}) for m in [self.data[id] for id in self.ids]], "documents": [m.get("document", "") for m in [self.data[id] for id in self.ids]]}
            
            def count(self):
                return len(self.ids)
            
            def add(self, ids, embeddings, documents, metadatas):
                for i, id in enumerate(ids):
                    self.data[id] = {
                        "id": id,
                        "embedding": embeddings[i] if i < len(embeddings) else None,
                        "document": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {}
                    }
                    self.ids.append(id)
        
        class MockEmbProxy:
            def embed_sync(self, texts, priority=100):
                return [[0.1] * 1024 for _ in texts]
        
        chroma_client = MockChromaClient()
        emb_proxy = MockEmbProxy()
        
        # 创建测试文档
        documents = [
            {"path": "/test/doc1.txt", "text": "Document 1 content"},
            {"path": "/test/doc2.txt", "text": "Document 2 content"},
        ]
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 使用实际的集合名称
        collection_name = get_active_collection("default_collection")
        
        # 正常全量重建
        count = build_full("default_collection", chroma_client, documents, emb_proxy, chunk_cfg)
        log("Build full completed", count > 0, f"chunks={count}")
        
        # 验证数据完整性
        collection = chroma_client.get_collection(collection_name)
        log("Collection created", collection is not None)
        log("Data integrity", collection.count() == count)
        
        # 模拟异常：在build_full过程中中断
        # 这里我们验证的是：如果旧集合被删除，新集合创建失败会发生什么
        original_delete = chroma_client.delete_collection
        def failing_delete(name):
            raise Exception("Simulated failure during delete")
        
        chroma_client.delete_collection = failing_delete
        
        try:
            # 这应该会失败，但旧数据应该还在
            build_full("default_collection", chroma_client, documents, emb_proxy, chunk_cfg)
        except Exception:
            pass
        
        chroma_client.delete_collection = original_delete
        
        # 验证：旧集合应该还在（因为删除失败）
        log("Old collection preserved on failure", 
            collection_name in chroma_client.collections)
        
    except Exception as e:
        log("Build full recovery test", False, str(e))


def test_data_integrity_after_crash():
    """测试2.4: 崩溃后数据完整性"""
    pr("\n--- Test 2.4: Data Integrity After Crash ---")
    
    try:
        from core.repository import DocumentRepository, content_hash
        
        class MockCollection:
            def __init__(self):
                self.data = {}
                self.ids = []
            
            def get(self, where=None, include=None):
                if where and "source" in where:
                    source = where["source"]
                    matching = [self.data[id] for id in self.ids if self.data[id].get("metadata", {}).get("source") == source]
                    if not matching:
                        return {"ids": [], "metadatas": [], "documents": []}
                    return {
                        "ids": [m["id"] for m in matching],
                        "metadatas": [m.get("metadata", {}) for m in matching],
                        "documents": [m.get("document", "") for m in matching]
                    }
                return {"ids": self.ids, "metadatas": [m.get("metadata", {}) for m in [self.data[id] for id in self.ids]], "documents": [m.get("document", "") for m in [self.data[id] for id in self.ids]]}
            
            def count(self):
                return len(self.ids)
            
            def add(self, ids, embeddings, documents, metadatas):
                for i, id in enumerate(ids):
                    self.data[id] = {
                        "id": id,
                        "embedding": embeddings[i] if i < len(embeddings) else None,
                        "document": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {}
                    }
                    self.ids.append(id)
            
            def delete(self, where=None):
                if where and "source" in where:
                    source = where["source"]
                    self.ids = [id for id in self.ids if self.data[id].get("metadata", {}).get("source") != source]
        
        class MockEmbProxy:
            def embed_sync(self, texts, priority=100):
                return [[0.1] * 1024 for _ in texts]
        
        collection = MockCollection()
        emb_proxy = MockEmbProxy()
        repo = DocumentRepository(collection, emb_proxy)
        
        chunk_cfg = {"chunk_size": 1000, "overlap": 100, "strategy": "flat", "separators": ["\n\n", "\n", " "]}
        
        # 添加多个文档
        docs = [
            {"path": "/test/doc1.txt", "text": "Document 1"},
            {"path": "/test/doc2.txt", "text": "Document 2"},
            {"path": "/test/doc3.txt", "text": "Document 3"},
        ]
        
        for doc in docs:
            repo.add(doc, chunk_cfg, source_type="local_file")
        
        initial_count = repo.count()
        log("Initial documents added", initial_count == 3, f"count={initial_count}")
        
        # 模拟崩溃：在批量操作中途失败
        call_count = [0]
        original_batch_add = repo._batch_add
        
        def failing_batch_add(chunks, batch_size=50):
            call_count[0] += 1
            if call_count[0] == 2:  # 第二批失败
                raise Exception("Simulated crash during batch add")
            return original_batch_add(chunks, batch_size)
        
        repo._batch_add = failing_batch_add
        
        # 尝试添加更多文档（会失败）
        new_docs = [
            {"path": "/test/doc4.txt", "text": "Document 4"},
            {"path": "/test/doc5.txt", "text": "Document 5"},
        ]
        
        try:
            for doc in new_docs:
                repo.add(doc, chunk_cfg, source_type="local_file")
        except Exception:
            pass
        
        repo._batch_add = original_batch_add
        
        # 验证：原始文档应该还在
        log("Original docs preserved after crash", repo.count() >= 3,
            f"count={repo.count()}")
        
        # 验证：数据一致性（没有损坏）
        for doc in docs:
            exists = repo.exists(doc["path"])
            log(f"Doc {Path(doc['path']).name} exists", exists)
        
    except Exception as e:
        log("Data integrity test", False, str(e))


def test_content_hash_consistency():
    """测试2.5: content_hash一致性"""
    pr("\n--- Test 2.5: Content Hash Consistency ---")
    
    try:
        from core.repository import content_hash
        from core.builder import content_hash as builder_content_hash
        
        # 验证两个模块的content_hash函数一致
        test_text = "Hello, this is a test document."
        
        repo_hash = content_hash(test_text)
        builder_hash = builder_content_hash(test_text)
        
        log("Hash functions consistent", repo_hash == builder_hash,
            f"repo={repo_hash}, builder={builder_hash}")
        
        # 验证相同内容产生相同hash
        hash1 = content_hash(test_text)
        hash2 = content_hash(test_text)
        log("Same content same hash", hash1 == hash2)
        
        # 验证不同内容产生不同hash
        hash3 = content_hash("Different content")
        log("Different content different hash", hash1 != hash3)
        
    except Exception as e:
        log("Content hash test", False, str(e))


# ==================== 主函数 ====================

def run_core_tests():
    """运行所有core模块测试"""
    pr("=" * 60)
    pr("  Ezy-RAG Core Module Tests")
    pr("=" * 60)
    pr(f"  Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pr("=" * 60)
    
    # 测试1: 异步并发
    test_scheduler_priority_queue()
    test_concurrent_query_and_build()
    test_multiple_concurrent_queries()
    
    # 测试2: ACID事务
    test_update_atomicity()
    test_sync_consistency()
    test_build_full_recovery()
    test_data_integrity_after_crash()
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

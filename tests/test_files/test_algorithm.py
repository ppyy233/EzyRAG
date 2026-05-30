"""
排序算法实现
包含冒泡排序、快速排序、归并排序三种经典排序算法
用于性能对比测试
"""
import time
import random
from typing import List


def bubble_sort(arr: List[int]) -> List[int]:
    """
    冒泡排序
    时间复杂度: O(n^2)
    空间复杂度: O(1)
    稳定性: 稳定
    """
    n = len(arr)
    result = arr.copy()
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
                swapped = True
        if not swapped:
            break
    return result


def quick_sort(arr: List[int]) -> List[int]:
    """
    快速排序
    时间复杂度: 平均 O(n log n)，最坏 O(n^2)
    空间复杂度: O(log n)
    稳定性: 不稳定
    """
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)


def merge_sort(arr: List[int]) -> List[int]:
    """
    归并排序
    时间复杂度: O(n log n)
    空间复杂度: O(n)
    稳定性: 稳定
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    return _merge(left, right)


def _merge(left: List[int], right: List[int]) -> List[int]:
    """合并两个有序数组"""
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def benchmark(sort_func, data: List[int]) -> float:
    """测量排序函数执行时间"""
    start = time.time()
    sort_func(data)
    return time.time() - start


if __name__ == "__main__":
    # 生成测试数据
    sizes = [100, 1000, 5000]
    for size in sizes:
        data = [random.randint(0, 10000) for _ in range(size)]
        print(f"\n数据规模: {size}")
        print(f"  冒泡排序: {benchmark(bubble_sort, data):.4f}s")
        print(f"  快速排序: {benchmark(quick_sort, data):.4f}s")
        print(f"  归并排序: {benchmark(merge_sort, data):.4f}s")

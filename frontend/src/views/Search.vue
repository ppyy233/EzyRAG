<template>
  <div class="search-page">
    <div class="page-header">
      <h2>搜索知识库</h2>
      <p>输入关键词，搜索相似文档</p>
    </div>

    <div class="search-box">
      <el-input
        v-model="query"
        placeholder="请输入搜索关键词..."
        size="large"
        @keyup.enter="handleSearch"
        clearable
      >
        <template #append>
          <el-button @click="handleSearch" :loading="loading" type="primary">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
        </template>
      </el-input>
    </div>

    <!-- 搜索结果 -->
    <div v-if="results.length > 0" class="results-section">
      <div class="results-header">
        <span class="results-title">搜索结果</span>
        <el-tag type="info">共 {{ results.length }} 条</el-tag>
        <el-tag v-if="rerankUsed" type="warning" size="small">已重排</el-tag>
      </div>

      <div class="results-list">
        <div v-for="(result, index) in results" :key="index" class="result-item">
          <div class="result-header">
            <span class="result-index">{{ index + 1 }}</span>
            <span class="result-source">{{ result.filename }}</span>
            <div class="result-scores">
              <el-tag :type="getSimilarityType(result.similarity)" size="small">
                相似度: {{ result.similarity }}%
              </el-tag>
              <el-tag v-if="result.rerank_score !== undefined" type="warning" size="small">
                重排: {{ result.rerank_score }}%
              </el-tag>
            </div>
          </div>
          <div class="result-content">
            {{ result.text }}
          </div>
        </div>
      </div>
    </div>

    <!-- 无结果提示（只在搜索完成且没有结果时显示） -->
    <div v-else-if="searched && !loading" class="no-results">
      <el-empty description="未找到相关文档" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { searchApi } from '../api'
import { ElMessage } from 'element-plus'

const query = ref('')
const results = ref([])
const loading = ref(false)
const searched = ref(false)
const rerankUsed = ref(false)

const getSimilarityType = (similarity) => {
  if (similarity >= 80) return 'success'
  if (similarity >= 60) return 'warning'
  return 'info'
}

const handleSearch = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  
  loading.value = true
  searched.value = false  // 搜索开始时设置为 false
  results.value = []      // 清空之前的结果
  rerankUsed.value = false
  
  try {
    const response = await searchApi.search(query.value)
    if (response.status === 'success') {
      results.value = response.data.results || []
      rerankUsed.value = response.data.rerank || false
      searched.value = true  // 搜索完成后设置为 true
      
      if (results.value.length === 0) {
        ElMessage.info('未找到相关文档')
      }
    } else {
      ElMessage.error(response.message)
      searched.value = true
    }
  } catch (error) {
    ElMessage.error('搜索失败')
    searched.value = true
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
}

.page-header p {
  font-size: 14px;
  color: #909399;
}

.search-box {
  margin-bottom: 30px;
}

.results-section {
  margin-bottom: 20px;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.results-title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background-color: #fafafa;
  transition: all 0.3s;
}

.result-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
}

.result-source {
  flex: 1;
  font-weight: bold;
  color: #303133;
}

.result-scores {
  display: flex;
  gap: 8px;
}

.result-content {
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.no-results {
  margin-bottom: 20px;
}
</style>

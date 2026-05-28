<template>
  <div class="search">
    <h1>搜索知识库</h1>
    
    <el-card class="search-box">
      <div class="search-input">
        <el-input
          v-model="query"
          placeholder="请输入搜索关键词..."
          size="large"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch" :loading="loading">
              <el-icon><Search /></el-icon>
              搜索
            </el-button>
          </template>
        </el-input>
      </div>
    </el-card>

    <el-card v-if="results.length > 0" class="search-results">
      <template #header>
        <div class="card-header">
          <span>搜索结果</span>
          <el-tag type="info">共 {{ results.length }} 条</el-tag>
        </div>
      </template>
      
      <div class="result-list">
        <div v-for="(result, index) in results" :key="index" class="result-item">
          <div class="result-header">
            <span class="result-index">{{ index + 1 }}</span>
            <span class="result-source">{{ result.source }}</span>
            <el-tag :type="getSimilarityType(result.similarity)" size="small">
              相似度: {{ (result.similarity * 100).toFixed(2) }}%
            </el-tag>
          </div>
          <div class="result-content">
            {{ result.content }}
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-else-if="searched" class="no-results">
      <el-empty description="未找到相关文档" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { search } from '../api'
import { ElMessage } from 'element-plus'

const query = ref('')
const results = ref([])
const loading = ref(false)
const searched = ref(false)

const getSimilarityType = (similarity) => {
  if (similarity >= 0.8) return 'success'
  if (similarity >= 0.6) return 'warning'
  return 'info'
}

const handleSearch = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  
  loading.value = true
  searched.value = true
  
  try {
    const response = await search(query.value)
    if (response.status === 'success') {
      results.value = response.data.results || []
      if (results.value.length === 0) {
        ElMessage.info('未找到相关文档')
      }
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    ElMessage.error('搜索失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.search {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 20px;
  color: #303133;
}

.search-box {
  margin-bottom: 20px;
}

.search-input {
  max-width: 800px;
  margin: 0 auto;
}

.search-results {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.result-item {
  padding: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background-color: #fafafa;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.result-index {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  font-weight: bold;
}

.result-source {
  flex: 1;
  font-weight: bold;
  color: #303133;
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

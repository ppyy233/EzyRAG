<template>
  <div class="home">
    <h1>Ezy-RAG 知识库管理系统</h1>
    
    <el-row :gutter="20" class="status-cards">
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>本地文档</span>
            </div>
          </template>
          <div class="card-content">
            <div class="stat-number">{{ status.local_documents || 0 }}</div>
            <div class="stat-label">个文档</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><DataBoard /></el-icon>
              <span>向量库文档</span>
            </div>
          </template>
          <div class="card-content">
            <div class="stat-number">{{ status.vector_documents || 0 }}</div>
            <div class="stat-label">个文档</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><List /></el-icon>
              <span>Chunks</span>
            </div>
          </template>
          <div class="card-content">
            <div class="stat-number">{{ status.total_chunks || 0 }}</div>
            <div class="stat-label">个向量</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><Connection /></el-icon>
              <span>服务状态</span>
            </div>
          </template>
          <div class="card-content">
            <el-tag :type="status.chromadb?.status === 'online' ? 'success' : 'danger'" size="large">
              ChromaDB: {{ status.chromadb?.status || 'unknown' }}
            </el-tag>
            <el-tag :type="status.embedding?.status === 'online' ? 'success' : 'danger'" size="large" style="margin-top: 10px;">
              Embedding: {{ status.embedding?.status || 'unknown' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="action-cards">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Operation /></el-icon>
              <span>快速操作</span>
            </div>
          </template>
          <div class="action-buttons">
            <el-button type="primary" @click="$router.push('/documents')">
              <el-icon><Document /></el-icon>
              文档管理
            </el-button>
            <el-button type="success" @click="$router.push('/search')">
              <el-icon><Search /></el-icon>
              搜索知识库
            </el-button>
            <el-button type="warning" @click="syncDocuments">
              <el-icon><Refresh /></el-icon>
              同步文档
            </el-button>
            <el-button type="danger" @click="rebuildDatabase">
              <el-icon><RefreshRight /></el-icon>
              全量重建
            </el-button>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><InfoFilled /></el-icon>
              <span>系统信息</span>
            </div>
          </template>
          <div class="system-info">
            <p><strong>集合名称：</strong>{{ status.collection || 'N/A' }}</p>
            <p><strong>总记录数：</strong>{{ status.total_records || 0 }}</p>
            <p><strong>ChromaDB：</strong>{{ status.chromadb?.url || 'N/A' }}</p>
            <p><strong>Embedding：</strong>{{ status.embedding?.url || 'N/A' }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getStatus, syncDocuments as syncApi, rebuildDatabase as rebuildApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const status = ref({})

const loadStatus = async () => {
  try {
    const response = await getStatus()
    if (response.status === 'success') {
      status.value = response.data
    }
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

const syncDocuments = async () => {
  try {
    await ElMessageBox.confirm('确定要同步本地文件和向量库吗？', '确认', {
      type: 'info'
    })
    
    const response = await syncApi()
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadStatus()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('同步失败')
    }
  }
}

const rebuildDatabase = async () => {
  try {
    await ElMessageBox.confirm('确定要全量重建向量库吗？这将清空现有数据！', '警告', {
      type: 'warning'
    })
    
    const response = await rebuildApi()
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadStatus()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重建失败')
    }
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #303133;
}

.status-cards {
  margin-bottom: 20px;
}

.status-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: bold;
}

.card-content {
  text-align: center;
  padding: 20px 0;
}

.stat-number {
  font-size: 48px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 10px;
}

.action-cards {
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.system-info p {
  margin: 10px 0;
  line-height: 1.6;
}
</style>

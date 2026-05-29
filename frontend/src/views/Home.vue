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
            <div class="stat-number">{{ status.total_documents || 0 }}</div>
            <div class="stat-label">个文档</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><DataBoard /></el-icon>
              <span>向量库记录</span>
            </div>
          </template>
          <div class="card-content">
            <div class="stat-number">{{ status.total_records || 0 }}</div>
            <div class="stat-label">条记录</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon><FolderOpened /></el-icon>
              <span>集合名称</span>
            </div>
          </template>
          <div class="card-content">
            <div class="stat-text">{{ status.collection || 'N/A' }}</div>
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
            <div v-for="svc in serviceList" :key="svc.name" class="service-row">
              <el-tag :type="svc.online ? 'success' : 'danger'" size="small">
                {{ svc.name }}: {{ svc.online ? '在线' : '离线' }}
              </el-tag>
            </div>
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
            <el-button type="warning" @click="syncDocuments" :loading="syncing">
              <el-icon><Refresh /></el-icon>
              同步文档
            </el-button>
            <el-button type="danger" @click="rebuildDatabase" :loading="rebuilding">
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
            <p><strong>Embedding 服务：</strong>{{ status.embedding?.url || 'N/A' }}</p>
            <p><strong>ChromaDB 服务：</strong>{{ status.chromadb?.url || 'N/A' }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStatus, getServices, syncDocuments as syncApi, rebuildDatabase as rebuildApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const status = ref({})
const services = ref([])
const syncing = ref(false)
const rebuilding = ref(false)

const serviceList = computed(() => {
  return services.value.map(s => ({
    name: s.name,
    online: s.status === 'online'
  }))
})

const loadStatus = async () => {
  try {
    const [statusRes, servicesRes] = await Promise.all([getStatus(), getServices()])
    if (statusRes.status === 'success') {
      status.value = statusRes.data
    }
    if (servicesRes.status === 'success') {
      services.value = servicesRes.data || []
    }
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

const syncDocuments = async () => {
  try {
    await ElMessageBox.confirm('确定要同步本地文件和向量库吗？', '确认', { type: 'info' })
    syncing.value = true
    const response = await syncApi()
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadStatus()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

const rebuildDatabase = async () => {
  try {
    await ElMessageBox.confirm('确定要全量重建向量库吗？这将清空现有数据！', '警告', { type: 'warning' })
    rebuilding.value = true
    const response = await rebuildApi()
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadStatus()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('重建失败')
  } finally {
    rebuilding.value = false
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

.stat-text {
  font-size: 14px;
  font-weight: bold;
  color: #409eff;
  word-break: break-all;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 10px;
}

.service-row {
  margin: 5px 0;
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

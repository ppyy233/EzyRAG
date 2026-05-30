<template>
  <div class="home">
    <div class="welcome-section">
      <h1>Ezy-RAG 知识库管理系统</h1>
      <p class="subtitle">智能文档管理 · 向量检索 · 知识问答</p>
    </div>

    <el-row :gutter="20" class="stats-section">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon">
            <el-icon :size="32" color="#409eff"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ status.database?.documents || 0 }}</div>
            <div class="stat-label">本地文档</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon">
            <el-icon :size="32" color="#67c23a"><DataBoard /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ status.database?.chunks || 0 }}</div>
            <div class="stat-label">向量块</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon">
            <el-icon :size="32" color="#e6a23c"><FolderOpened /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-text">{{ status.database?.collection || 'N/A' }}</div>
            <div class="stat-label">当前集合</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon">
            <el-icon :size="32" color="#f56c6c"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ onlineCount }}/{{ totalCount }}</div>
            <div class="stat-label">服务在线</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="actions-section">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Operation /></el-icon>
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <div class="action-item" @click="$router.push('/documents')">
              <el-icon :size="40" color="#409eff"><Document /></el-icon>
              <div class="action-info">
                <div class="action-title">文档管理</div>
                <div class="action-desc">管理本地文档，导入、同步、重建向量库</div>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="action-item" @click="$router.push('/search')">
              <el-icon :size="40" color="#67c23a"><Search /></el-icon>
              <div class="action-info">
                <div class="action-title">搜索知识库</div>
                <div class="action-desc">搜索相似文档，支持语义检索</div>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="action-item" @click="$router.push('/config')">
              <el-icon :size="40" color="#e6a23c"><Setting /></el-icon>
              <div class="action-info">
                <div class="action-title">配置管理</div>
                <div class="action-desc">配置 Embedding、Rerank、切片参数</div>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="action-item" @click="$router.push('/services')">
              <el-icon :size="40" color="#f56c6c"><Monitor /></el-icon>
              <div class="action-info">
                <div class="action-title">服务管理</div>
                <div class="action-desc">查看和管理后端服务状态</div>
              </div>
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><InfoFilled /></el-icon>
              <span>系统信息</span>
            </div>
          </template>
          <div class="system-info">
            <div class="info-item">
              <span class="info-label">版本</span>
              <span class="info-value">{{ status.version || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Embedding</span>
              <el-tag :type="status.services?.embedding?.online ? 'success' : 'danger'" size="small">
                {{ status.services?.embedding?.mode || 'N/A' }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="info-label">Rerank</span>
              <el-tag :type="status.services?.rerank?.online ? 'success' : 'danger'" size="small">
                {{ status.services?.rerank?.mode || 'N/A' }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="info-label">ChromaDB</span>
              <el-tag :type="status.services?.chromadb?.online ? 'success' : 'danger'" size="small">
                {{ status.services?.chromadb?.online ? '在线' : '离线' }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="info-label">MCP</span>
              <el-tag :type="status.services?.mcp?.online ? 'success' : 'danger'" size="small">
                {{ status.services?.mcp?.online ? '在线' : '离线' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { systemApi } from '../api'
import { ArrowRight } from '@element-plus/icons-vue'

const status = ref({})

const onlineCount = computed(() => {
  const services = status.value.services || {}
  return Object.values(services).filter(s => s.online).length
})

const totalCount = computed(() => {
  const services = status.value.services || {}
  return Object.keys(services).length
})

const loadStatus = async () => {
  try {
    const response = await systemApi.health()
    if (response.status === 'success') {
      status.value = response.data
    }
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-section {
  text-align: center;
  margin-bottom: 30px;
}

.welcome-section h1 {
  font-size: 28px;
  color: #303133;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: #909399;
}

.stats-section {
  margin-bottom: 20px;
}

.stat-card {
  height: 100%;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.stat-icon {
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-text {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  word-break: break-all;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.actions-section {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.action-item:hover {
  border-color: #409eff;
  background-color: #f5f7fa;
}

.action-info {
  flex: 1;
}

.action-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 4px;
}

.action-desc {
  font-size: 12px;
  color: #909399;
}

.system-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 14px;
  color: #606266;
}

.info-value {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
}
</style>

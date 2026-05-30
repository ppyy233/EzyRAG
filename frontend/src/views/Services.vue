<template>
  <div class="services-page">
    <div class="page-header">
      <h2>服务管理</h2>
      <p>查看和管理后端服务状态</p>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="startAll" :loading="batchLoading">
        <el-icon><VideoPlay /></el-icon>
        启动所有
      </el-button>
      <el-button type="danger" @click="stopAll" :loading="batchLoading">
        <el-icon><VideoPause /></el-icon>
        停止所有
      </el-button>
      <el-button @click="refreshStatus" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
    </div>

    <el-table :data="services" stripe>
      <el-table-column label="服务" width="150">
        <template #default="scope">
          <div class="service-name">
            <el-icon :size="16" :color="scope.row.online ? '#67c23a' : '#f56c6c'">
              <CircleCheck v-if="scope.row.online" />
              <CircleClose v-else />
            </el-icon>
            <span>{{ scope.row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="模式" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.mode === 'cloud' ? 'warning' : 'primary'" size="small">
            {{ scope.row.mode === 'cloud' ? '云端' : '本地' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="地址" min-width="200">
        <template #default="scope">
          <span v-if="scope.row.mode === 'cloud'">{{ scope.row.url || 'API 服务' }}</span>
          <span v-else>{{ scope.row.host }}:{{ scope.row.port }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="scope">
          <el-tag :type="scope.row.online ? 'success' : 'danger'" size="default">
            {{ scope.row.online ? '运行中' : '未运行' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="scope">
          <el-button 
            size="small" type="primary" 
            @click="startService(scope.row)" 
            :disabled="scope.row.online || scope.row.mode === 'cloud'"
            :loading="scope.row._starting"
          >
            {{ scope.row._starting ? '启动中...' : '启动' }}
          </el-button>
          <el-button size="small" type="danger" @click="stopService(scope.row)" :disabled="!scope.row.online || scope.row.mode === 'cloud'">
            停止
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { systemApi, servicesApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, CircleCheck, CircleClose, VideoPlay, VideoPause } from '@element-plus/icons-vue'

const services = ref([])
const loading = ref(false)
const batchLoading = ref(false)

const refreshStatus = async () => {
  loading.value = true
  try {
    const response = await systemApi.status()
    if (response.status === 'success') {
      const data = response.data
      
      services.value = [
        { 
          key: 'chromadb', name: 'ChromaDB', mode: 'local',
          host: data.chromadb?.host || '127.0.0.1',
          port: data.chromadb?.port || 9898, 
          online: data.chromadb?.online || false, _starting: false 
        },
      ]
      
      const embMode = data.embedding?.mode || 'cloud'
      services.value.push({
        key: 'embedding', name: 'Embedding', mode: embMode,
        host: embMode === 'local' ? (data.embedding?.host || '127.0.0.1') : null,
        port: embMode === 'local' ? (data.embedding?.port || 1234) : null,
        url: embMode === 'cloud' ? (data.embedding?.config?.url || 'API 服务') : null,
        online: data.embedding?.online || false, _starting: false
      })
      
      const rerankMode = data.rerank?.mode || 'local'
      if (data.rerank?.enabled !== false) {
        services.value.push({
          key: 'rerank', name: 'Rerank', mode: rerankMode,
          host: rerankMode === 'local' ? (data.rerank?.host || '127.0.0.1') : null,
          port: rerankMode === 'local' ? (data.rerank?.port || 5001) : null,
          url: rerankMode === 'cloud' ? (data.rerank?.config?.url || 'API 服务') : null,
          online: data.rerank?.online || false, _starting: false
        })
      }
      
      services.value.push({
        key: 'mcp', name: 'MCP', mode: 'local',
        host: data.mcp?.host || '127.0.0.1',
        port: data.mcp?.port || 9766,
        online: data.mcp?.online || false, _starting: false
      })
    }
  } catch (error) {
    console.error('获取服务状态失败:', error)
  } finally {
    loading.value = false
  }
}

const startService = async (service) => {
  service._starting = true
  try {
    const response = await servicesApi.start(service.key)
    if (response.status === 'success') {
      ElMessage.success(response.message || `${service.name} 启动中`)
      setTimeout(refreshStatus, 3000)
    } else {
      ElMessage.error(response.message || '启动失败')
    }
  } catch (error) {
    ElMessage.error(`启动 ${service.name} 失败`)
  } finally {
    service._starting = false
  }
}

const stopService = async (service) => {
  try {
    await ElMessageBox.confirm(`确定要停止 ${service.name} 吗？`, '确认', { type: 'warning' })
    const response = await servicesApi.stop(service.key)
    if (response.status === 'success') {
      ElMessage.success(response.message || `${service.name} 已停止`)
      refreshStatus()
    } else {
      ElMessage.error(response.message || '停止失败')
    }
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(`停止 ${service.name} 失败`)
  }
}

const startAll = async () => {
  batchLoading.value = true
  try {
    for (const service of services.value) {
      if (!service.online && service.mode === 'local') {
        await startService(service)
      }
    }
    ElMessage.success('启动完成')
    await refreshStatus()
  } catch (error) {
    ElMessage.error(`启动失败: ${error.message}`)
  } finally {
    batchLoading.value = false
  }
}

const stopAll = async () => {
  try {
    await ElMessageBox.confirm('确定要停止所有本地服务吗？', '确认', { type: 'warning' })
    batchLoading.value = true
    for (const service of services.value) {
      if (service.online && service.mode === 'local') {
        await stopService(service)
      }
    }
    ElMessage.success('停止完成')
    await refreshStatus()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(`停止失败: ${error.message}`)
  } finally {
    batchLoading.value = false
  }
}

onMounted(refreshStatus)
</script>

<style scoped>
.services-page {
  max-width: 1000px;
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

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.service-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
}
</style>

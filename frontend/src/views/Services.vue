<template>
  <div class="services">
    <h1>服务管理</h1>
    
    <el-card class="service-status">
      <template #header>
        <div class="card-header">
          <span>服务状态</span>
          <el-button @click="refreshStatus">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <el-table :data="services" stripe>
        <el-table-column prop="name" label="服务名称" width="150" />
        <el-table-column prop="port" label="端口" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'online' ? 'success' : 'danger'">
              {{ scope.row.status === 'online' ? '运行中' : '未运行' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pid" label="PID" width="100" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" type="primary" @click="startService(scope.row)" :disabled="scope.row.status === 'online'">
              启动
            </el-button>
            <el-button size="small" type="danger" @click="stopService(scope.row)" :disabled="scope.row.status !== 'online'">
              停止
            </el-button>
            <el-button size="small" type="warning" @click="restartService(scope.row)" :disabled="scope.row.status !== 'online'">
              重启
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHealth } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const services = ref([
  { name: 'ChromaDB', port: 9898, status: 'unknown', pid: '-' },
  { name: 'MCP Server', port: 9766, status: 'unknown', pid: '-' },
  { name: 'API Server', port: 9767, status: 'unknown', pid: '-' },
  { name: 'Rerank Server', port: 5001, status: 'unknown', pid: '-' },
  { name: 'Embedding 服务', port: 5000, status: 'unknown', pid: '-' }
])

const refreshStatus = async () => {
  try {
    const response = await getHealth()
    if (response.status === 'success') {
      const data = response.data
      services.value = services.value.map(service => {
        if (service.name === 'ChromaDB') {
          return { ...service, status: data.chromadb?.status || 'unknown' }
        }
        if (service.name === 'Embedding 服务') {
          return { ...service, status: data.embedding?.status || 'unknown' }
        }
        return service
      })
    }
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

const startService = async (service) => {
  ElMessage.info(`启动 ${service.name}...`)
  // 这里应该调用后端 API 启动服务
}

const stopService = async (service) => {
  try {
    await ElMessageBox.confirm(`确定要停止 ${service.name} 吗？`, '确认', {
      type: 'warning'
    })
    ElMessage.info(`停止 ${service.name}...`)
    // 这里应该调用后端 API 停止服务
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('停止失败')
    }
  }
}

const restartService = async (service) => {
  try {
    await ElMessageBox.confirm(`确定要重启 ${service.name} 吗？`, '确认', {
      type: 'warning'
    })
    ElMessage.info(`重启 ${service.name}...`)
    // 这里应该调用后端 API 重启服务
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重启失败')
    }
  }
}

onMounted(refreshStatus)
</script>

<style scoped>
.services {
  max-width: 1000px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 20px;
  color: #303133;
}

.service-status {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

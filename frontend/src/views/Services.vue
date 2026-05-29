<template>
  <div class="services">
    <h1>服务管理</h1>
    
    <el-card class="service-status">
      <template #header>
        <div class="card-header">
          <span>服务状态</span>
          <el-button @click="refreshStatus" :loading="loading">
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
        <el-table-column prop="pid" label="PID" width="100">
          <template #default="scope">
            <span :class="{ 'pid-active': scope.row.status === 'online' }">{{ scope.row.pid }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="scope">
            <el-button 
              size="small" type="primary" 
              @click="startService(scope.row)" 
              :disabled="scope.row.status === 'online'"
              :loading="scope.row._starting"
            >
              {{ scope.row._starting ? '启动中...' : '启动' }}
            </el-button>
            <el-button size="small" type="danger" @click="stopService(scope.row)" :disabled="scope.row.status !== 'online'">
              停止
            </el-button>
            <el-button size="small" type="warning" @click="restartService(scope.row)" :disabled="scope.row.status !== 'online'" :loading="scope.row._restarting">
              重启
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="startingService" class="start-progress">
        <div class="progress-text">
          正在启动 {{ startingService.name }}...
          <span v-if="startCountdown > 0">（预计 {{ startCountdown }} 秒）</span>
        </div>
        <el-progress :percentage="startPercent" :status="startPercent >= 100 ? 'success' : ''" :stroke-width="20" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getServices, startService as startServiceApi, stopService as stopServiceApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const services = ref([])
const loading = ref(false)
const startingService = ref(null)
const startPercent = ref(0)
const startCountdown = ref(0)

const refreshStatus = async () => {
  loading.value = true
  try {
    const response = await getServices()
    if (response.status === 'success') {
      services.value = (response.data || []).map(s => ({
        ...s,
        _starting: false,
        _restarting: false
      }))
    }
  } catch (error) {
    console.error('获取服务状态失败:', error)
  } finally {
    loading.value = false
  }
}

const pollUntilOnline = async (key, maxWait = 45000) => {
  const startTime = Date.now()
  const interval = 1000

  while (Date.now() - startTime < maxWait) {
    try {
      const response = await getServices()
      if (response.status === 'success') {
        const svc = (response.data || []).find(s => s.key === key)
        if (svc && svc.status === 'online') {
          return true
        }
      }
    } catch (e) { /* skip */ }

    const elapsed = Date.now() - startTime
    startPercent.value = Math.min(95, Math.round(elapsed / maxWait * 100))
    startCountdown.value = Math.max(0, Math.ceil((maxWait - elapsed) / 1000))

    await new Promise(r => setTimeout(r, interval))
  }
  return false
}

const startService = async (service) => {
  service._starting = true
  startingService.value = service
  startPercent.value = 5
  startCountdown.value = 45

  try {
    await startServiceApi(service.key)
    const ok = await pollUntilOnline(service.key)
    if (ok) {
      startPercent.value = 100
      startCountdown.value = 0
      ElMessage.success(`${service.name} 启动成功`)
    } else {
      ElMessage.warning(`${service.name} 启动超时，请检查日志`)
    }
  } catch (error) {
    ElMessage.error(`启动 ${service.name} 失败`)
  } finally {
    service._starting = false
    setTimeout(() => {
      startingService.value = null
      startPercent.value = 0
      refreshStatus()
    }, 1500)
  }
}

const stopService = async (service) => {
  try {
    await ElMessageBox.confirm(`确定要停止 ${service.name} 吗？`, '确认', { type: 'warning' })
    const response = await stopServiceApi(service.key)
    if (response.status === 'success') {
      ElMessage.success(response.message)
    } else {
      ElMessage.error(response.message)
    }
    refreshStatus()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(`停止 ${service.name} 失败`)
  }
}

const restartService = async (service) => {
  try {
    await ElMessageBox.confirm(`确定要重启 ${service.name} 吗？`, '确认', { type: 'warning' })
    service._restarting = true
    await stopServiceApi(service.key)
    await new Promise(r => setTimeout(r, 2000))

    startingService.value = service
    startPercent.value = 5
    startCountdown.value = 45

    await startServiceApi(service.key)
    const ok = await pollUntilOnline(service.key)
    if (ok) {
      startPercent.value = 100
      ElMessage.success(`${service.name} 重启成功`)
    } else {
      ElMessage.warning(`${service.name} 重启超时`)
    }
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(`重启 ${service.name} 失败`)
  } finally {
    service._restarting = false
    setTimeout(() => {
      startingService.value = null
      startPercent.value = 0
      refreshStatus()
    }, 1500)
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

.pid-active {
  color: #67c23a;
  font-weight: bold;
}

.start-progress {
  margin-top: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.progress-text {
  margin-bottom: 10px;
  color: #606266;
}
</style>

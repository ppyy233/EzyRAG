import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.response.use(
  response => {
    const data = response.data
    if (data.status === 'error') {
      ElMessage.error(data.message || '操作失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  error => {
    console.error('API Error:', error)
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

// 系统
export const systemApi = {
  health: () => api.get('/system/health'),
  status: () => api.get('/system/status')
}

// 配置
export const configApi = {
  get: () => api.get('/config'),
  update: (data) => api.put('/config', data),
  templates: () => api.get('/config/templates'),
  getChunk: () => api.get('/config/chunk'),
  updateChunk: (data) => api.put('/config/chunk', data)
}

// 文档
export const documentsApi = {
  list: (source = 'all') => api.get(`/documents?source=${source}`),
  upload: (files) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return api.post('/documents/upload', formData, {
      timeout: 300000,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  importFiles: (files) => api.post('/documents/import', { files }),
  importAll: () => api.post('/documents/import-all'),
  batchImport: (files) => api.post('/documents/batch-import', { files }),
  delete: (filePath) => api.delete(`/documents/${encodeURIComponent(filePath)}`),
  batchDelete: (files) => api.post('/documents/batch-delete', { files }),
  deleteAll: (source = 'all') => api.post('/documents/delete-all', { source }),
  updateFile: (filePath) => api.post('/documents/update', { file_path: filePath }),
  sync: (source = 'all') => api.post('/documents/sync', { source }),
  rebuild: (source = 'all') => api.post('/documents/rebuild', { source }),
  cleanOrphans: (source = 'all') => api.post('/documents/clean-orphans', { source }),
  crawl: (url) => api.post('/documents/crawl', { url })
}

// 搜索
export const searchApi = {
  search: (query) => api.post('/search', { query })
}

// 服务管理
export const servicesApi = {
  start: (service) => api.post('/services/start', { service }),
  stop: (service) => api.post('/services/stop', { service })
}

export function createWebSocket(onMessage) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws`
  
  const ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket connected')
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (onMessage) {
        onMessage(data)
      }
    } catch (e) {
      console.error('WebSocket message parse error:', e)
    }
  }
  
  ws.onclose = () => {
    console.log('WebSocket disconnected')
    setTimeout(() => {
      console.log('WebSocket reconnecting...')
      createWebSocket(onMessage)
    }, 3000)
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
  
  return ws
}

export default api

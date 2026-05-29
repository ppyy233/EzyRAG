import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 状态
export const getStatus = () => api.get('/status')

// 文档
export const getDocuments = () => api.get('/documents')
export const addDocument = (filePath) => api.post('/documents', { file_path: filePath })
export const deleteDocument = (filePath) => api.delete('/documents', { data: { file_path: filePath } })
export const updateDocument = (filePath) => api.put('/documents', { file_path: filePath })
export const uploadDocument = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 同步
export const syncDocuments = () => api.post('/sync')
export const rebuildDatabase = () => api.post('/rebuild')

// 向量库文档管理
export const getVectorDocs = () => api.get('/vector-docs')
export const deleteVectorDoc = (source) => api.delete('/vector-docs', { data: { source } })
export const cancelVectorization = () => api.post('/documents/cancel')

// 搜索
export const search = (query) => api.post('/search', { query })

// 配置
export const getConfig = () => api.get('/config')
export const saveConfig = (data) => api.put('/config', data)

// 服务管理
export const getServices = () => api.get('/services')
export const startService = (key) => api.post(`/services/${key}/start`)
export const stopService = (key) => api.post(`/services/${key}/stop`)

// 健康检查
export const getHealth = () => api.get('/health')

export default api

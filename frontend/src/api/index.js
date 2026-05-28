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

// 搜索
export const search = (query) => api.post('/search', { query })

// 健康检查
export const getHealth = () => api.get('/health')

export default api

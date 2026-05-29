<template>
  <div class="documents">
    <h1>文档管理</h1>

    <el-tabs v-model="activeTab" type="border-card">

      <!-- Tab 1: 本地文件 -->
      <el-tab-pane label="本地文件" name="local">
        <div class="tab-toolbar">
          <el-button type="primary" @click="importSelected" :disabled="selectedLocal.length === 0 || importingLock" :loading="importingLock && currentAction === 'selected'">
            <el-icon><Plus /></el-icon> 导入选中 ({{ selectedLocal.length }})
          </el-button>
          <el-button type="success" @click="importAll" :disabled="importingLock" :loading="importingLock && currentAction === 'all'">
            <el-icon><Plus /></el-icon> 导入全部
          </el-button>
          <el-button v-if="importingLock" type="danger" @click="stopVectorization">
            <el-icon><VideoPause /></el-icon> 停止向量化
          </el-button>
          <el-button @click="refreshLocal" :disabled="importingLock">
            <el-icon><RefreshRight /></el-icon> 刷新
          </el-button>
        </div>

        <div class="upload-drop" @dragover.prevent @drop.prevent="handleDrop">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">拖拽文件或文件夹到此处上传到本地</div>
          <div class="upload-buttons">
            <label class="el-button el-button--primary el-button--small">
              <el-icon><Document /></el-icon> 选择文件
              <input type="file" multiple hidden @change="handleFileInput" />
            </label>
            <label class="el-button el-button--success el-button--small">
              <el-icon><FolderOpened /></el-icon> 选择文件夹
              <input type="file" webkitdirectory multiple hidden @change="handleFolderInput" />
            </label>
          </div>
        </div>

        <div v-if="uploadFileList.length > 0" class="upload-info">
          <span>已选择 {{ uploadFileList.length }} 个文件</span>
          <el-button type="primary" size="small" @click="uploadFiles" :loading="uploadLoading" style="margin-left:10px">上传</el-button>
          <el-button size="small" @click="uploadFileList = []">清空</el-button>
        </div>

        <el-table :data="pagedLocalDocs" @selection-change="s => selectedLocal = s" stripe style="margin-top:15px">
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="文件名" min-width="200" />
          <el-table-column prop="in_vector" label="向量库" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.in_vector ? 'success' : 'info'" size="small">
                {{ scope.row.in_vector ? '已导入' : '未导入' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunks" label="Chunks" width="80" />
          <el-table-column label="操作" width="180">
            <template #default="scope">
              <el-button size="small" type="primary" @click="importDoc(scope.row)" :disabled="scope.row.in_vector || importingLock" :loading="scope.row._loading">导入</el-button>
              <el-button size="small" type="warning" @click="updateDoc(scope.row)" :disabled="!scope.row.in_vector || importingLock" :loading="scope.row._loading">更新</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-bar">
          <el-pagination v-model:current-page="localPage" :page-size="pageSize" :total="localDocs.length" layout="total, prev, pager, next" />
        </div>
      </el-tab-pane>

      <!-- Tab 2: 向量库文档 -->
      <el-tab-pane label="向量库文档" name="vector">
        <div class="tab-toolbar">
          <el-button type="danger" @click="deleteSelectedVector" :disabled="selectedVector.length === 0">
            <el-icon><Delete /></el-icon> 删除选中 ({{ selectedVector.length }})
          </el-button>
          <el-button type="warning" @click="deleteAllVector">
            <el-icon><Delete /></el-icon> 清空向量库
          </el-button>
          <el-button @click="refreshVector">
            <el-icon><RefreshRight /></el-icon> 刷新
          </el-button>
          <span class="vector-summary">共 {{ vectorDocs.length }} 个文档，{{ vectorTotalChunks }} 个 chunks</span>
        </div>

        <el-table :data="pagedVectorDocs" @selection-change="s => selectedVector = s" stripe style="margin-top:15px">
          <el-table-column type="selection" width="55" />
          <el-table-column label="文件名" min-width="250">
            <template #default="scope">{{ getFileName(scope.row.source) }}</template>
          </el-table-column>
          <el-table-column prop="source" label="来源路径" min-width="350" show-overflow-tooltip />
          <el-table-column prop="chunks" label="Chunks" width="100" />
          <el-table-column label="操作" width="100">
            <template #default="scope">
              <el-button size="small" type="danger" @click="deleteVectorDoc(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-bar">
          <el-pagination v-model:current-page="vectorPage" :page-size="pageSize" :total="vectorDocs.length" layout="total, prev, pager, next" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 进度 + 日志窗口 -->
    <el-card v-if="progress.visible" class="progress-card">
      <template #header>
        <div class="progress-header">
          <span>{{ progress.text }}</span>
          <el-button v-if="importingLock" type="danger" size="small" @click="stopVectorization">
            停止向量化
          </el-button>
        </div>
      </template>
      <el-progress :percentage="progress.percent" :status="progress.status" :stroke-width="20" />
      <div class="log-window" ref="logWindow">
        <div v-for="(log, index) in progressLogs" :key="index" class="log-line">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg" :class="{ 'log-error': log.type === 'error', 'log-success': log.type === 'success' }">{{ log.message }}</span>
        </div>
        <div v-if="progressLogs.length === 0" class="log-empty">等待日志...</div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import {
  getDocuments, addDocument, deleteDocument, updateDocument, uploadDocument,
  getVectorDocs, deleteVectorDoc as deleteVectorDocApi, cancelVectorization
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('local')
const pageSize = 20

// ===== 本地文件 =====
const localDocs = ref([])
const selectedLocal = ref([])
const localPage = ref(1)
const uploadFileList = ref([])
const uploadLoading = ref(false)

const pagedLocalDocs = computed(() => {
  const start = (localPage.value - 1) * pageSize
  return localDocs.value.slice(start, start + pageSize)
})

const loadLocalDocs = async () => {
  try {
    const response = await getDocuments()
    if (response.status === 'success') {
      localDocs.value = (response.data.documents || []).map(d => ({ ...d, _loading: false }))
    }
  } catch (e) { console.error(e) }
}

// ===== 向量库文档 =====
const vectorDocs = ref([])
const selectedVector = ref([])
const vectorPage = ref(1)

const pagedVectorDocs = computed(() => {
  const start = (vectorPage.value - 1) * pageSize
  return vectorDocs.value.slice(start, start + pageSize)
})

const vectorTotalChunks = computed(() => vectorDocs.value.reduce((s, d) => s + d.chunks, 0))
const getFileName = (source) => source.split(/[/\\]/).pop()

const loadVectorDocs = async () => {
  try {
    const response = await getVectorDocs()
    if (response.status === 'success') {
      vectorDocs.value = response.data.documents || []
    }
  } catch (e) { console.error(e) }
}

// ===== 进度 + 日志 =====
const progress = reactive({ visible: false, text: '', percent: 0, status: '' })
const progressLogs = ref([])
const logWindow = ref(null)
const importingLock = ref(false)
const cancelRequested = ref(false)
const currentAction = ref('')

const addLog = (message, type = 'info') => {
  progressLogs.value.push({ time: new Date().toLocaleTimeString(), message, type })
  nextTick(() => {
    if (logWindow.value) logWindow.value.scrollTop = logWindow.value.scrollHeight
  })
}

const showProgress = (text, percent = 0, status = '') => {
  progress.visible = true
  progress.text = text
  progress.percent = percent
  progress.status = status
}

const hideProgress = () => {
  progress.visible = false
  progress.text = ''
  progress.percent = 0
  progress.status = ''
}

const stopVectorization = async () => {
  cancelRequested.value = true
  try {
    await cancelVectorization()
    addLog('已发送停止请求，等待当前批次完成...', 'error')
    ElMessage.info('已发送停止请求')
  } catch (e) { /* skip */ }
}

// ===== 文件过滤 =====
const SUPPORTED_EXT = new Set(['.txt','.md','.pdf','.docx','.py','.js','.ts','.java','.c','.cpp','.go','.rs','.r','.sh','.sql','.json','.yaml','.yml','.csv','.xml','.toml','.html','.css'])
const filterFiles = (files) => Array.from(files).filter(f => SUPPORTED_EXT.has('.' + f.name.split('.').pop().toLowerCase()))

const handleFileInput = (e) => { uploadFileList.value.push(...filterFiles(e.target.files)); e.target.value = '' }
const handleFolderInput = (e) => { uploadFileList.value.push(...filterFiles(e.target.files)); e.target.value = '' }

const readEntryRecursive = (entry) => new Promise(resolve => {
  if (entry.isFile) entry.file(f => resolve([f]), () => resolve([]))
  else if (entry.isDirectory) {
    const reader = entry.createReader()
    reader.readEntries(async entries => {
      const files = []
      for (const e of entries) files.push(...await readEntryRecursive(e))
      resolve(files)
    }, () => resolve([]))
  } else resolve([])
})

const handleDrop = async (e) => {
  const files = []
  for (const item of e.dataTransfer.items) {
    if (item.kind === 'file') {
      const entry = item.webkitGetAsEntry?.()
      if (entry) files.push(...await readEntryRecursive(entry))
      else { const f = item.getAsFile(); if (f) files.push(f) }
    }
  }
  uploadFileList.value.push(...filterFiles(files))
}

// ===== 操作 =====
const importDoc = async (doc) => {
  if (importingLock.value) { ElMessage.warning('正在导入中，请等待完成或点击停止'); return }
  importingLock.value = true
  cancelRequested.value = false
  currentAction.value = 'single'
  progressLogs.value = []
  showProgress(`正在导入: ${doc.name}...`, 0)
  addLog(`开始导入: ${doc.name}`)
  doc._loading = true
  try {
    const r = await addDocument(doc.path)
    if (r.status === 'success') {
      addLog(`完成: ${doc.name} - ${r.message}`, 'success')
      showProgress('导入完成', 100, 'success')
      loadLocalDocs(); loadVectorDocs()
    } else {
      addLog(`失败: ${doc.name} - ${r.message}`, 'error')
      showProgress('导入失败', 100, 'exception')
    }
  } catch (e) {
    addLog(`失败: ${doc.name} - ${e.message}`, 'error')
    showProgress('导入失败', 100, 'exception')
  } finally {
    doc._loading = false
    importingLock.value = false
    currentAction.value = ''
  }
}

const updateDoc = async (doc) => {
  if (importingLock.value) { ElMessage.warning('正在导入中，请等待完成或点击停止'); return }
  importingLock.value = true
  cancelRequested.value = false
  currentAction.value = 'single'
  progressLogs.value = []
  showProgress(`正在更新: ${doc.name}...`, 0)
  addLog(`开始更新: ${doc.name}`)
  doc._loading = true
  try {
    const r = await updateDocument(doc.path)
    if (r.status === 'success') {
      addLog(`完成: ${doc.name} - ${r.message}`, 'success')
      showProgress('更新完成', 100, 'success')
      loadLocalDocs(); loadVectorDocs()
    } else {
      addLog(`失败: ${doc.name} - ${r.message}`, 'error')
      showProgress('更新失败', 100, 'exception')
    }
  } catch (e) {
    addLog(`失败: ${doc.name} - ${e.message}`, 'error')
    showProgress('更新失败', 100, 'exception')
  } finally {
    doc._loading = false
    importingLock.value = false
    currentAction.value = ''
  }
}

const importSelected = async () => {
  const docs = selectedLocal.value.filter(d => !d.in_vector)
  if (!docs.length) return
  if (importingLock.value) { ElMessage.warning('正在导入中，请等待完成或点击停止'); return }
  importingLock.value = true
  cancelRequested.value = false
  currentAction.value = 'selected'
  progressLogs.value = []
  showProgress('批量导入中...', 0)
  addLog(`开始批量导入 ${docs.length} 个文件`)
  let done = 0
  let success = 0
  let failed = 0
  for (const doc of docs) {
    if (cancelRequested.value) {
      addLog(`用户停止，已处理 ${done}/${docs.length} 个文件`, 'error')
      break
    }
    addLog(`[${done + 1}/${docs.length}] 正在导入: ${doc.name}`)
    showProgress(`[${done + 1}/${docs.length}] ${doc.name}`, Math.round(done / docs.length * 100))
    try {
      const r = await addDocument(doc.path)
      if (r.status === 'success') {
        addLog(`  完成: ${r.message}`, 'success')
        success++
      } else {
        addLog(`  失败: ${r.message}`, 'error')
        failed++
      }
    } catch (e) {
      addLog(`  失败: ${e.message}`, 'error')
      failed++
    }
    done++
    showProgress(`[${done}/${docs.length}] 完成`, Math.round(done / docs.length * 100))
  }
  addLog(`批量导入结束: 成功 ${success}，失败 ${failed}，共 ${done}/${docs.length}`, success > 0 ? 'success' : 'error')
  showProgress(`导入完成 (${success}/${docs.length})`, 100, failed === 0 ? 'success' : 'exception')
  importingLock.value = false
  currentAction.value = ''
  loadLocalDocs(); loadVectorDocs()
}

const importAll = async () => {
  const docs = localDocs.value.filter(d => !d.in_vector)
  if (!docs.length) { ElMessage.info('没有需要导入的文件'); return }
  if (importingLock.value) { ElMessage.warning('正在导入中，请等待完成或点击停止'); return }
  try { await ElMessageBox.confirm(`确定导入 ${docs.length} 个文件到向量库？`, '确认', { type: 'info' }) } catch { return }
  importingLock.value = true
  cancelRequested.value = false
  currentAction.value = 'all'
  progressLogs.value = []
  showProgress('批量导入中...', 0)
  addLog(`开始导入全部 ${docs.length} 个文件`)
  let done = 0
  let success = 0
  let failed = 0
  for (const doc of docs) {
    if (cancelRequested.value) {
      addLog(`用户停止，已处理 ${done}/${docs.length} 个文件`, 'error')
      break
    }
    addLog(`[${done + 1}/${docs.length}] 正在导入: ${doc.name}`)
    showProgress(`[${done + 1}/${docs.length}] ${doc.name}`, Math.round(done / docs.length * 100))
    try {
      const r = await addDocument(doc.path)
      if (r.status === 'success') {
        addLog(`  完成: ${r.message}`, 'success')
        success++
      } else {
        addLog(`  失败: ${r.message}`, 'error')
        failed++
      }
    } catch (e) {
      addLog(`  失败: ${e.message}`, 'error')
      failed++
    }
    done++
    showProgress(`[${done}/${docs.length}] 完成`, Math.round(done / docs.length * 100))
  }
  addLog(`导入结束: 成功 ${success}，失败 ${failed}，共 ${done}/${docs.length}`, success > 0 ? 'success' : 'error')
  showProgress(`导入完成 (${success}/${docs.length})`, 100, failed === 0 ? 'success' : 'exception')
  importingLock.value = false
  currentAction.value = ''
  loadLocalDocs(); loadVectorDocs()
}

const deleteVectorDoc = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定从向量库删除 ${getFileName(doc.source)}？`, '确认', { type: 'warning' })
    const r = await deleteVectorDocApi(doc.source)
    if (r.status === 'success') { ElMessage.success(r.message); loadLocalDocs(); loadVectorDocs() }
    else ElMessage.error(r.message)
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const deleteSelectedVector = async () => {
  if (!selectedVector.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedVector.value.length} 个文档？`, '警告', { type: 'warning' })
    for (const doc of selectedVector.value) await deleteVectorDocApi(doc.source)
    ElMessage.success('删除完成'); loadLocalDocs(); loadVectorDocs()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const deleteAllVector = async () => {
  if (!vectorDocs.value.length) return
  try {
    await ElMessageBox.confirm(`确定清空整个向量库（${vectorDocs.value.length} 个文档）？`, '警告', { type: 'warning' })
    for (const doc of vectorDocs.value) await deleteVectorDocApi(doc.source)
    ElMessage.success('向量库已清空'); loadLocalDocs(); loadVectorDocs()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const uploadFiles = async () => {
  if (!uploadFileList.value.length) return
  uploadLoading.value = true
  showProgress('上传中...', 0)
  progressLogs.value = []
  let done = 0
  for (const file of uploadFileList.value) {
    addLog(`上传: ${file.name}`)
    try { await uploadDocument(file); addLog(`  完成`, 'success') } catch { addLog(`  失败`, 'error') }
    done++
    showProgress(`上传中... (${done}/${uploadFileList.value.length})`, Math.round(done / uploadFileList.value.length * 100))
  }
  showProgress('上传完成', 100, 'success')
  uploadFileList.value = []; uploadLoading.value = false
  loadLocalDocs()
}

const refreshLocal = () => { localPage.value = 1; loadLocalDocs() }
const refreshVector = () => { vectorPage.value = 1; loadVectorDocs() }

onMounted(() => { loadLocalDocs(); loadVectorDocs() })
</script>

<style scoped>
.documents { max-width: 1200px; margin: 0 auto; }
h1 { margin-bottom: 20px; color: #303133; }
.tab-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
.vector-summary { margin-left: auto; color: #909399; font-size: 14px; }
.upload-drop {
  border: 2px dashed #dcdfe6; border-radius: 8px; padding: 25px 40px;
  text-align: center; cursor: pointer; transition: border-color 0.3s;
}
.upload-drop:hover { border-color: #409eff; }
.upload-icon { font-size: 40px; color: #c0c4cc; }
.upload-text { color: #606266; margin: 8px 0; }
.upload-buttons { display: flex; gap: 10px; justify-content: center; margin-top: 8px; }
.upload-info { margin-top: 10px; display: flex; align-items: center; }
.pagination-bar { display: flex; justify-content: center; margin-top: 15px; }
.progress-card { margin-top: 20px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; }
.log-window {
  margin-top: 15px; max-height: 300px; overflow-y: auto;
  background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px;
  font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.6;
}
.log-line { display: flex; gap: 10px; }
.log-time { color: #6a9955; white-space: nowrap; }
.log-msg { color: #d4d4d4; }
.log-error { color: #f44747; }
.log-success { color: #6a9955; }
.log-empty { color: #808080; font-style: italic; }
</style>

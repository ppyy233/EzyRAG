<template>
  <div class="documents-page">
    <div class="page-header">
      <h2>文档管理</h2>
      <p>管理本地文档和向量库，支持增量同步、批量操作</p>
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="selectedSource" @change="handleSourceChange" style="width: 140px;">
          <el-option label="全部数据" value="all" />
          <el-option label="本地文档" value="docs" />
          <el-option label="网页数据" value="web" />
        </el-select>
        <el-divider direction="vertical" />
        <el-button type="primary" @click="batchImport" :loading="batchImporting" :disabled="selectedLocalCount === 0">
          <el-icon><Upload /></el-icon>
          <span>批量导入 ({{ selectedLocalCount }})</span>
        </el-button>
        <el-button type="danger" @click="batchDelete" :loading="batchDeleting" :disabled="selectedImportedCount === 0">
          <el-icon><Delete /></el-icon>
          <span>批量删除 ({{ selectedImportedCount }})</span>
        </el-button>
        <el-button type="danger" @click="deleteAll" :loading="deletingAll">
          <el-icon><Delete /></el-icon>
          <span>完全删除</span>
        </el-button>
      </div>
      <div class="toolbar-right">
        <template v-if="progress.visible">
          <el-button type="danger" @click="stopOperation">
            <el-icon><VideoPause /></el-icon>
            <span>停止</span>
          </el-button>
        </template>
        <el-button v-else @click="syncDocs" :loading="syncing">
          <el-icon><Refresh /></el-icon>
          <span>增量同步</span>
        </el-button>
        <el-button type="warning" @click="rebuildDocs" :loading="rebuilding">
          <el-icon><RefreshRight /></el-icon>
          <span>全量重建</span>
        </el-button>
        <el-button @click="cleanOrphans" :loading="cleaning">
          <el-icon><Delete /></el-icon>
          <span>清理孤立</span>
        </el-button>
        <el-button @click="refresh">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="progress.visible" class="progress-section">
      <div class="progress-info">
        <div class="progress-current">当前: {{ progress.currentFile }}</div>
        <div class="progress-step">步骤: {{ progress.step }}</div>
      </div>
      <el-progress
        :percentage="progress.percentage"
        :status="progress.status"
        :stroke-width="20"
        striped
        striped-flow
      >
        <span>{{ progress.text }}</span>
      </el-progress>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 文档列表 -->
      <el-tab-pane label="文档列表" name="list">
        <!-- 拖拽上传 -->
        <div class="upload-area" 
             @dragover.prevent="dragover" 
             @dragleave="dragleave" 
             @drop.prevent="handleDrop"
             :class="{ 'is-dragover': isDragover }"
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">
            拖拽文件或文件夹到此处，或 <em>点击选择</em>
          </div>
          <div class="upload-buttons">
            <label class="el-button el-button--primary el-button--small">
              <el-icon><Document /></el-icon> 选择文件
              <input type="file" multiple hidden @change="handleFileSelect" />
            </label>
            <label class="el-button el-button--success el-button--small">
              <el-icon><FolderOpened /></el-icon> 选择文件夹
              <input type="file" webkitdirectory multiple hidden @change="handleFileSelect" />
            </label>
          </div>
          <div class="el-upload__tip">支持 PDF、DOCX、TXT、MD 等格式，文件将自动复制到 data/docs 目录</div>
        </div>

        <!-- 文档表格 -->
        <el-table :data="paginatedDocuments" stripe v-loading="loading" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="文件名" min-width="200" />
          <el-table-column label="来源" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.source_type === 'web' ? 'success' : 'primary'" size="small">
                {{ scope.row.source_type === 'web' ? '网页' : '本地' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">
                {{ getStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunks" label="Chunks" width="100" />
          <el-table-column label="操作" width="250">
            <template #default="scope">
              <el-button
                v-if="scope.row.status === 'local'"
                type="primary"
                size="small"
                @click="importDoc(scope.row)"
                :loading="scope.row.importing"
              >
                导入
              </el-button>
              <el-button
                v-if="scope.row.status === 'imported'"
                type="success"
                size="small"
                @click="updateDoc(scope.row)"
                :loading="scope.row.updating"
              >
                更新
              </el-button>
              <el-button
                v-if="scope.row.status === 'imported'"
                type="danger"
                size="small"
                @click="deleteDoc(scope.row)"
                :loading="scope.row.deleting"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="documents.length"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </el-tab-pane>

      <!-- 网页爬取 -->
      <el-tab-pane label="网页爬取" name="crawl">
        <div class="crawl-section">
          <h3>网页爬取</h3>
          <p>输入网页 URL，自动爬取内容并添加到向量库</p>
          <el-form label-width="100px">
            <el-form-item label="网页 URL">
              <el-input v-model="crawlUrl" placeholder="https://example.com" size="large" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="crawlWeb" :loading="crawling" size="large">
                <el-icon><Download /></el-icon>
                <span>开始爬取</span>
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { documentsApi, createWebSocket } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Refresh, RefreshRight, Delete, Download, VideoPause, Document, FolderOpened } from '@element-plus/icons-vue'

const activeTab = ref('list')
const documents = ref([])
const loading = ref(false)
const syncing = ref(false)
const rebuilding = ref(false)
const cleaning = ref(false)
const crawling = ref(false)
const crawlUrl = ref('')

const selectedSource = ref('all')
const selectedDocs = ref([])
const batchImporting = ref(false)
const batchDeleting = ref(false)
const deletingAll = ref(false)
const isDragover = ref(false)

const currentPage = ref(1)
const pageSize = ref(20)

const progress = ref({
  visible: false,
  percentage: 0,
  text: '',
  status: '',
  currentFile: '',
  step: ''
})

let ws = null

const paginatedDocuments = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return documents.value.slice(start, end)
})

const selectedLocalCount = computed(() => {
  return selectedDocs.value.filter(d => d.status === 'local').length
})

const selectedImportedCount = computed(() => {
  return selectedDocs.value.filter(d => d.status === 'imported').length
})

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
}

const handleCurrentChange = (val) => {
  currentPage.value = val
}

const handleSourceChange = async () => {
  await refresh()
}

const dragover = () => {
  isDragover.value = true
}

const dragleave = () => {
  isDragover.value = false
}

const handleDrop = async (event) => {
  isDragover.value = false
  const files = []
  const seen = new Set()

  const items = event.dataTransfer.items
  if (items) {
    for (const item of items) {
      const entry = item.webkitGetAsEntry?.()
      if (entry) {
        await readEntry(entry, files, seen)
      }
    }
  } else {
    for (const file of event.dataTransfer.files) {
      files.push(file)
    }
  }

  if (files.length > 0) {
    await uploadFiles(files)
  }
}

const readEntry = async (entry, files, seen) => {
  if (entry.isFile) {
    const file = await new Promise(resolve => entry.file(resolve))
    const key = `${file.name}_${file.size}`
    if (!seen.has(key)) {
      seen.add(key)
      files.push(file)
    }
  } else if (entry.isDirectory) {
    const reader = entry.createReader()
    const entries = await new Promise(resolve => reader.readEntries(resolve))
    for (const e of entries) {
      await readEntry(e, files, seen)
    }
  }
}

const handleFileSelect = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  
  const filesToUpload = []
  for (const file of files) {
    filesToUpload.push(file)
  }
  
  if (filesToUpload.length > 0) {
    await uploadFiles(filesToUpload)
  }
  event.target.value = ''
}

const uploadFiles = async (files) => {
  showProgress(`正在上传 ${files.length} 个文件...`, 0, '', '准备中...', '上传中...')
  
  try {
    const result = await documentsApi.upload(files)
    showProgress(`上传完成: ${result.data.count} 个文件`, 100, 'success', '完成', `已上传到 data/docs 目录`)
    ElMessage.success(`上传完成: ${result.data.count} 个文件`)
    await refresh()
  } catch (e) {
    showProgress('上传失败', 100, 'exception', '失败', e.message)
    ElMessage.error(`上传失败: ${e.message}`)
  } finally {
    setTimeout(hideProgress, 3000)
  }
}

const handleSelectionChange = (selection) => {
  selectedDocs.value = selection
}

const showProgress = (text, percentage = 0, status = '', currentFile = '', step = '') => {
  progress.value = { visible: true, percentage, text, status, currentFile, step }
}

const hideProgress = () => {
  progress.value.visible = false
}

const getStatusType = (status) => {
  switch (status) {
    case 'imported': return 'success'
    case 'local': return 'info'
    case 'orphan': return 'warning'
    default: return ''
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'imported': return '已导入'
    case 'local': return '未导入'
    case 'orphan': return '孤立'
    default: return status
  }
}

const refresh = async () => {
  loading.value = true
  try {
    const result = await documentsApi.list(selectedSource.value)
    documents.value = result.data.map(doc => ({
      ...doc,
      importing: false,
      updating: false,
      deleting: false
    }))
  } catch (e) {
    console.error('Failed to fetch documents:', e)
  } finally {
    loading.value = false
  }
}

const handleFileChange = async (file) => {
  const filePath = file.raw.path || file.name
  await importDoc({ name: file.name, path: filePath, importing: false })
}

const importDoc = async (doc) => {
  doc.importing = true
  showProgress(`导入: ${doc.name}`, 0, '', doc.name, '正在读取文件...')
  try {
    const result = await documentsApi.importFiles([doc.path])
    if (result.data.results[0].status === 'success') {
      showProgress(`导入成功: ${doc.name}`, 100, 'success', doc.name, `完成 (${result.data.results[0].chunks} chunks)`)
      ElMessage.success(`导入成功: ${doc.name}`)
    } else {
      showProgress(`导入失败: ${doc.name}`, 100, 'exception', doc.name, result.data.results[0].message)
      ElMessage.error(`导入失败: ${doc.name}`)
    }
    await refresh()
  } catch (e) {
    showProgress(`导入失败: ${doc.name}`, 100, 'exception', doc.name, e.message)
    ElMessage.error(`导入失败: ${doc.name}`)
  } finally {
    doc.importing = false
    setTimeout(hideProgress, 3000)
  }
}

const updateDoc = async (doc) => {
  doc.updating = true
  showProgress(`更新: ${doc.name}`, 0, '', doc.name, '正在读取文件...')
  try {
    const result = await documentsApi.updateFile(doc.path)
    if (result.status === 'success') {
      showProgress(`更新成功: ${doc.name}`, 100, 'success', doc.name, `完成 (${result.data.chunks} chunks)`)
      ElMessage.success(`更新成功: ${doc.name}`)
    } else {
      showProgress(`更新失败: ${doc.name}`, 100, 'exception', doc.name, result.message)
      ElMessage.error(`更新失败: ${doc.name}`)
    }
    await refresh()
  } catch (e) {
    showProgress(`更新失败: ${doc.name}`, 100, 'exception', doc.name, e.message)
    ElMessage.error(`更新失败: ${doc.name}`)
  } finally {
    doc.updating = false
    setTimeout(hideProgress, 3000)
  }
}

const deleteDoc = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定要删除 ${doc.name} 的向量记录吗？`, '确认删除', { type: 'warning' })
    doc.deleting = true
    showProgress(`删除: ${doc.name}`, 0, '', doc.name, '正在删除...')
    await documentsApi.delete(doc.path)
    showProgress(`删除成功: ${doc.name}`, 100, 'success', doc.name, '完成')
    ElMessage.success(`删除成功: ${doc.name}`)
    await refresh()
  } catch (e) {
    if (e !== 'cancel') {
      showProgress(`删除失败: ${doc.name}`, 100, 'exception', doc.name, e.message)
      ElMessage.error(`删除失败: ${doc.name}`)
    }
  } finally {
    doc.deleting = false
    setTimeout(hideProgress, 3000)
  }
}

const batchImport = async () => {
  const files = selectedDocs.value.filter(d => d.status === 'local').map(d => d.path)
  if (files.length === 0) {
    ElMessage.warning('没有选中未导入的文件')
    return
  }
  batchImporting.value = true
  showProgress(`批量导入 ${files.length} 个文件...`, 0, '', '准备中...', '开始导入')
  try {
    const result = await documentsApi.batchImport(files)
    showProgress(`批量导入完成: ${result.data.imported} 个文件`, 100, 'success', '完成', `${result.data.total_chunks} chunks`)
    ElMessage.success(`批量导入完成: ${result.data.imported} 个文件`)
    selectedDocs.value = []
    await refresh()
  } catch (e) {
    showProgress('批量导入失败', 100, 'exception', '失败', e.message)
    ElMessage.error(`批量导入失败: ${e.message}`)
  } finally {
    batchImporting.value = false
    setTimeout(hideProgress, 3000)
  }
}

const batchDelete = async () => {
  const files = selectedDocs.value.filter(d => d.status === 'imported').map(d => d.path)
  if (files.length === 0) {
    ElMessage.warning('没有选中已导入的文件')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${files.length} 个文件的向量记录吗？`, '确认批量删除', { type: 'warning' })
    batchDeleting.value = true
    showProgress(`批量删除 ${files.length} 个文件...`, 0, '', '准备中...', '开始删除')
    const result = await documentsApi.batchDelete(files)
    showProgress(`批量删除完成: ${result.data.deleted} 个文件`, 100, 'success', '完成', `删除 ${result.data.deleted} 个文件`)
    ElMessage.success(`批量删除完成: ${result.data.deleted} 个文件`)
    selectedDocs.value = []
    await refresh()
  } catch (e) {
    if (e !== 'cancel') {
      showProgress('批量删除失败', 100, 'exception', '失败', e.message)
      ElMessage.error(`批量删除失败: ${e.message}`)
    }
  } finally {
    batchDeleting.value = false
    setTimeout(hideProgress, 3000)
  }
}

const deleteAll = async () => {
  try {
    await ElMessageBox.confirm('确定要完全删除所有文档的向量记录吗？此操作不可撤销！', '确认完全删除', { 
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    })
    deletingAll.value = true
    showProgress('完全删除所有文档...', 0, '', '准备中...', '开始删除')
    const result = await documentsApi.deleteAll(selectedSource.value)
    showProgress(`完全删除完成: ${result.data.deleted} 个文件`, 100, 'success', '完成', `删除 ${result.data.deleted} 个文件`)
    ElMessage.success(`完全删除完成: ${result.data.deleted} 个文件`)
    selectedDocs.value = []
    await refresh()
  } catch (e) {
    if (e !== 'cancel') {
      showProgress('完全删除失败', 100, 'exception', '失败', e.message)
      ElMessage.error(`完全删除失败: ${e.message}`)
    }
  } finally {
    deletingAll.value = false
    setTimeout(hideProgress, 3000)
  }
}

const syncDocs = async () => {
  syncing.value = true
  showProgress('增量同步中...', 0, '', '准备中...', '开始同步')
  try {
    const result = await documentsApi.sync(selectedSource.value)
    const stats = result.data
    showProgress('同步完成', 100, 'success', '完成', `新增 ${stats.added}, 更新 ${stats.updated}, 未变 ${stats.unchanged}, 删除 ${stats.deleted}`)
    ElMessage.success('同步完成')
    await refresh()
  } catch (e) {
    showProgress('同步失败', 100, 'exception', '失败', e.message)
    ElMessage.error(`同步失败: ${e.message}`)
  } finally {
    syncing.value = false
    setTimeout(hideProgress, 3000)
  }
}

const rebuildDocs = async () => {
  try {
    await ElMessageBox.confirm('确定要全量重建向量库吗？这将清空现有数据并重新处理所有文档。', '确认重建', { type: 'warning' })
    rebuilding.value = true
    showProgress('全量重建中...', 0, '', '准备中...', '开始重建')
    const result = await documentsApi.rebuild(selectedSource.value)
    showProgress('重建完成', 100, 'success', '完成', `${result.data.chunks} chunks, ${result.data.documents} 文档`)
    ElMessage.success('重建完成')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') {
      showProgress('重建失败', 100, 'exception', '失败', e.message)
      ElMessage.error(`重建失败: ${e.message}`)
    }
  } finally {
    rebuilding.value = false
    setTimeout(hideProgress, 3000)
  }
}

const cleanOrphans = async () => {
  cleaning.value = true
  showProgress('清理孤立记录...', 0, '', '准备中...', '开始清理')
  try {
    const result = await documentsApi.cleanOrphans(selectedSource.value)
    if (result.data.cleaned === 0) {
      showProgress('没有孤立记录', 100, 'success', '完成', '没有孤立记录')
      ElMessage.info('没有孤立记录')
    } else {
      showProgress(`清理完成: ${result.data.cleaned} 个孤立记录`, 100, 'success', '完成', `清理 ${result.data.cleaned} 个孤立记录`)
      ElMessage.success(`清理完成: ${result.data.cleaned} 个孤立记录`)
    }
    await refresh()
  } catch (e) {
    showProgress('清理失败', 100, 'exception', '失败', e.message)
    ElMessage.error(`清理失败: ${e.message}`)
  } finally {
    cleaning.value = false
    setTimeout(hideProgress, 3000)
  }
}

const crawlWeb = async () => {
  if (!crawlUrl.value) {
    ElMessage.warning('请输入网页 URL')
    return
  }
  crawling.value = true
  showProgress(`爬取: ${crawlUrl.value}`, 0, '', crawlUrl.value, '正在爬取...')
  try {
    const result = await documentsApi.crawl(crawlUrl.value)
    showProgress(`爬取成功: ${result.data.title}`, 100, 'success', crawlUrl.value, `完成 (${result.data.chunks} chunks)`)
    ElMessage.success(`爬取成功: ${result.data.chunks} chunks`)
    crawlUrl.value = ''
    await refresh()
  } catch (e) {
    showProgress('爬取失败', 100, 'exception', crawlUrl.value, e.message)
    ElMessage.error(`爬取失败: ${e.message}`)
  } finally {
    crawling.value = false
    setTimeout(hideProgress, 3000)
  }
}

const stopOperation = async () => {
  try {
    await ElMessageBox.confirm('确定要停止当前操作吗？', '确认停止', { type: 'warning' })
    showProgress('已停止', 100, 'exception', '已停止', '用户取消')
    ElMessage.info('操作已停止')
    syncing.value = false
    rebuilding.value = false
    cleaning.value = false
    batchImporting.value = false
    batchDeleting.value = false
    deletingAll.value = false
    crawling.value = false
    setTimeout(hideProgress, 1000)
  } catch (e) {
    // 用户取消停止
  }
}

onMounted(() => {
  refresh()
  ws = createWebSocket((data) => {
    if (data.type === 'import_progress') {
      const d = data.data
      const percent = Math.round(d.idx / d.total * 100)
      if (d.status === 'success') {
        showProgress(`[${d.idx}/${d.total}] 导入: ${d.file}`, percent, '', d.file, `完成 (${d.chunks} chunks)`)
      } else {
        showProgress(`[${d.idx}/${d.total}] 导入失败: ${d.file}`, percent, 'exception', d.file, d.message)
      }
    } else if (data.type === 'sync_progress') {
      const d = data.data
      const percent = Math.round(d.idx / d.total * 100)
      if (d.op === 'copy') {
        showProgress(`复制: ${d.idx}/${d.total}`, percent, '', d.name, '复制数据')
      } else if (d.op === 'add') {
        showProgress(`[${d.idx}/${d.total}] 新增: ${d.name}`, percent, '', d.name, `新增 ${d.count} chunks`)
      } else if (d.op === 'update') {
        showProgress(`[${d.idx}/${d.total}] 更新: ${d.name}`, percent, '', d.name, `更新 ${d.count} chunks`)
      } else if (d.op === 'delete') {
        showProgress(`删除: ${d.name}`, percent, '', d.name, '删除')
      }
    } else if (data.type === 'sync_complete') {
      showProgress('同步完成', 100, 'success', '完成', '同步完成')
    } else if (data.type === 'rebuild_progress') {
      const d = data.data
      if (d.op === 'rebuild') {
        const percent = Math.round(d.idx / d.total * 100)
        showProgress(`[${d.idx}/${d.total}] ${d.name}`, percent, '', d.name, `重建 ${d.count} chunks`)
      }
    } else if (data.type === 'rebuild_complete') {
      showProgress('重建完成', 100, 'success', '完成', '重建完成')
    } else if (data.type === 'batch_progress') {
      const d = data.data
      const percent = Math.round(d.idx / d.total * 100)
      if (d.op === 'import') {
        if (d.status === 'success') {
          showProgress(`[${d.idx}/${d.total}] 导入: ${d.name}`, percent, '', d.name, `完成 (${d.chunks} chunks)`)
        } else {
          showProgress(`[${d.idx}/${d.total}] 导入失败: ${d.name}`, percent, 'exception', d.name, d.message)
        }
      } else if (d.op === 'delete') {
        if (d.status === 'success') {
          showProgress(`[${d.idx}/${d.total}] 删除: ${d.name}`, percent, '', d.name, '完成')
        } else {
          showProgress(`[${d.idx}/${d.total}] 删除失败: ${d.name}`, percent, 'exception', d.name, d.message)
        }
      }
    } else if (data.type === 'batch_complete') {
      const d = data.data
      if (d.op === 'import') {
        showProgress(`批量导入完成: ${d.imported} 个文件`, 100, 'success', '完成', `${d.total_chunks} chunks`)
      } else if (d.op === 'delete') {
        showProgress(`批量删除完成: ${d.deleted} 个文件`, 100, 'success', '完成', `删除 ${d.deleted} 个文件`)
      }
    }
  })
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.documents-page {
  max-width: 1200px;
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
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-section {
  margin-bottom: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.progress-current, .progress-step {
  font-size: 14px;
  color: #303133;
}

.upload-area {
  margin-bottom: 16px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  transition: all 0.3s;
  cursor: pointer;
  background: #fafafa;
}

.upload-area:hover,
.upload-area.is-dragover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.upload-area .el-icon--upload {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.upload-area .el-upload__text {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.upload-area .el-upload__text em {
  color: #409eff;
  font-style: normal;
}

.upload-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 12px;
}

.upload-area .el-upload__tip {
  font-size: 12px;
  color: #909399;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.crawl-section {
  padding: 20px;
}

.crawl-section h3 {
  margin-bottom: 8px;
  color: #303133;
}

.crawl-section p {
  margin-bottom: 16px;
  color: #909399;
}
</style>

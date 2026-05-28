<template>
  <div class="documents">
    <h1>文档管理</h1>
    
    <el-card class="action-bar">
      <div class="action-buttons">
        <el-button type="primary" @click="addSelected" :disabled="selectedDocs.length === 0">
          <el-icon><Plus /></el-icon>
          添加选中 ({{ selectedDocs.length }})
        </el-button>
        <el-button type="danger" @click="deleteSelected" :disabled="selectedDocs.length === 0">
          <el-icon><Delete /></el-icon>
          删除选中 ({{ selectedDocs.length }})
        </el-button>
        <el-button type="success" @click="addAll">
          <el-icon><Plus /></el-icon>
          添加全部
        </el-button>
        <el-button type="warning" @click="deleteAll">
          <el-icon><Delete /></el-icon>
          删除全部
        </el-button>
        <el-button @click="syncDocuments">
          <el-icon><Refresh /></el-icon>
          同步
        </el-button>
        <el-button @click="refresh">
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </div>
      
      <div class="upload-area">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :on-change="handleFileChange"
          multiple
          drag
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或 <em>点击上传</em>
          </div>
        </el-upload>
        <el-button type="primary" @click="uploadFiles" :disabled="uploadFiles.length === 0">
          上传文件
        </el-button>
      </div>
    </el-card>

    <el-card class="document-table">
      <el-table :data="documents" @selection-change="handleSelectionChange" stripe>
        <el-table-column type="selection" width="55" />
        <el-table-column prop="name" label="文件名" min-width="200" />
        <el-table-column prop="path" label="路径" min-width="300" />
        <el-table-column prop="in_vector" label="向量库状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.in_vector ? 'success' : 'info'">
              {{ scope.row.in_vector ? '已添加' : '未添加' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunks" label="Chunks" width="100" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" type="primary" @click="addDoc(scope.row)" :disabled="scope.row.in_vector">
              添加
            </el-button>
            <el-button size="small" type="warning" @click="updateDoc(scope.row)" :disabled="!scope.row.in_vector">
              更新
            </el-button>
            <el-button size="small" type="danger" @click="deleteDoc(scope.row)" :disabled="!scope.row.in_vector">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDocuments, addDocument, deleteDocument, updateDocument, uploadDocument, syncDocuments as syncApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const documents = ref([])
const selectedDocs = ref([])
const uploadFileList = ref([])
const uploadRef = ref(null)

const loadDocuments = async () => {
  try {
    const response = await getDocuments()
    if (response.status === 'success') {
      documents.value = response.data.documents
    }
  } catch (error) {
    console.error('获取文档失败:', error)
  }
}

const handleSelectionChange = (selection) => {
  selectedDocs.value = selection
}

const handleFileChange = (file) => {
  uploadFileList.value.push(file.raw)
}

const addDoc = async (doc) => {
  try {
    const response = await addDocument(doc.path)
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadDocuments()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const deleteDoc = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定要删除 ${doc.name} 吗？`, '确认', {
      type: 'warning'
    })
    
    const response = await deleteDocument(doc.path)
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadDocuments()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const updateDoc = async (doc) => {
  try {
    const response = await updateDocument(doc.path)
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadDocuments()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const addSelected = async () => {
  for (const doc of selectedDocs.value) {
    if (!doc.in_vector) {
      await addDoc(doc)
    }
  }
}

const deleteSelected = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedDocs.value.length} 个文档吗？`, '确认', {
      type: 'warning'
    })
    
    for (const doc of selectedDocs.value) {
      if (doc.in_vector) {
        await deleteDoc(doc)
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const addAll = async () => {
  try {
    await ElMessageBox.confirm('确定要添加所有本地文档到向量库吗？', '确认', {
      type: 'info'
    })
    
    for (const doc of documents.value) {
      if (!doc.in_vector) {
        await addDoc(doc)
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('添加失败')
    }
  }
}

const deleteAll = async () => {
  try {
    await ElMessageBox.confirm('确定要删除向量库中的所有文档吗？', '警告', {
      type: 'warning'
    })
    
    for (const doc of documents.value) {
      if (doc.in_vector) {
        await deleteDoc(doc)
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const syncDocuments = async () => {
  try {
    const response = await syncApi()
    if (response.status === 'success') {
      ElMessage.success(response.message)
      loadDocuments()
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    ElMessage.error('同步失败')
  }
}

const uploadFiles = async () => {
  for (const file of uploadFiles.value) {
    try {
      const response = await uploadDocument(file)
      if (response.status === 'success') {
        ElMessage.success(response.message)
      } else {
        ElMessage.error(response.message)
      }
    } catch (error) {
      ElMessage.error('上传失败')
    }
  }
  uploadFiles.value = []
  loadDocuments()
}

const refresh = () => {
  loadDocuments()
}

onMounted(loadDocuments)
</script>

<style scoped>
.documents {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 20px;
  color: #303133;
}

.action-bar {
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.upload-area {
  display: flex;
  align-items: center;
  gap: 20px;
}

.document-table {
  margin-bottom: 20px;
}
</style>

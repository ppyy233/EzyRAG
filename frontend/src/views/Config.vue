<template>
  <div class="config">
    <h1>配置管理</h1>
    
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>环境变量配置</span>
          <el-button type="primary" @click="saveConfig">
            <el-icon><Check /></el-icon>
            保存配置
          </el-button>
        </div>
      </template>
      
      <el-form :model="config" label-width="150px">
        <el-form-item label="Embedding 服务地址">
          <el-input v-model="config.EMBEDDING_API_URL" placeholder="http://127.0.0.1:5000/v1/embeddings" />
        </el-form-item>
        <el-form-item label="Embedding API Key">
          <el-input v-model="config.EMBEDDING_API_KEY" type="password" placeholder="可选" />
        </el-form-item>
        <el-form-item label="Embedding 模型">
          <el-input v-model="config.EMBEDDING_MODEL" placeholder="text-embedding-qwen3-embedding-4b" />
        </el-form-item>
        <el-form-item label="Embedding 维度">
          <el-input-number v-model="config.EMBEDDING_DIM" :min="1" :max="4096" />
        </el-form-item>
        
        <el-divider />
        
        <el-form-item label="Rerank 启用">
          <el-switch v-model="config.RERANK_ENABLED" />
        </el-form-item>
        <el-form-item label="Rerank 服务地址">
          <el-input v-model="config.RERANK_API_URL" placeholder="http://127.0.0.1:5001" />
        </el-form-item>
        <el-form-item label="Rerank API Key">
          <el-input v-model="config.RERANK_API_KEY" type="password" placeholder="可选" />
        </el-form-item>
        
        <el-divider />
        
        <el-form-item label="ChromaDB 地址">
          <el-input v-model="config.CHROMA_SERVER_HOST" placeholder="127.0.0.1" />
        </el-form-item>
        <el-form-item label="ChromaDB 端口">
          <el-input-number v-model="config.CHROMA_SERVER_PORT" :min="1" :max="65535" />
        </el-form-item>
        
        <el-divider />
        
        <el-form-item label="MCP 服务地址">
          <el-input v-model="config.MCP_SERVER_HOST" placeholder="127.0.0.1" />
        </el-form-item>
        <el-form-item label="MCP 服务端口">
          <el-input-number v-model="config.MCP_SERVER_PORT" :min="1" :max="65535" />
        </el-form-item>
        
        <el-divider />
        
        <el-form-item label="切块模板">
          <el-select v-model="config.CHUNK_TEMPLATE" placeholder="选择模板">
            <el-option label="英文文献专用" value="academic" />
            <el-option label="中文专用" value="chinese" />
            <el-option label="代码专用" value="code" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const config = ref({
  EMBEDDING_API_URL: 'http://127.0.0.1:5000/v1/embeddings',
  EMBEDDING_API_KEY: '',
  EMBEDDING_MODEL: 'text-embedding-qwen3-embedding-4b',
  EMBEDDING_DIM: 2560,
  RERANK_ENABLED: true,
  RERANK_API_URL: 'http://127.0.0.1:5001',
  RERANK_API_KEY: '',
  CHROMA_SERVER_HOST: '127.0.0.1',
  CHROMA_SERVER_PORT: 9898,
  MCP_SERVER_HOST: '127.0.0.1',
  MCP_SERVER_PORT: 9766,
  CHUNK_TEMPLATE: 'academic'
})

const loadConfig = async () => {
  // 这里应该从后端加载配置
  // 暂时使用默认值
}

const saveConfig = async () => {
  // 这里应该保存配置到后端
  ElMessage.success('配置保存成功')
}

onMounted(loadConfig)
</script>

<style scoped>
.config {
  max-width: 800px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 20px;
  color: #303133;
}

.config-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

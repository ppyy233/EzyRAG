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
        <el-form-item label="Rerank 模型">
          <el-input v-model="config.RERANK_MODEL" placeholder="远程 API 需要，本地服务可留空" />
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

        <template v-if="config.CHUNK_TEMPLATE === 'custom'">
          <el-form-item label="chunk_size">
            <el-input-number v-model="customChunk.chunk_size" :min="100" :max="10000" :step="100" />
            <span class="form-hint">单个切片最大字符数</span>
          </el-form-item>
          <el-form-item label="overlap">
            <el-input-number v-model="customChunk.overlap" :min="0" :max="1000" :step="10" />
            <span class="form-hint">相邻切片重叠字符数</span>
          </el-form-item>
          <el-form-item label="strategy">
            <el-select v-model="customChunk.strategy">
              <el-option label="recursive（推荐，保留段落结构）" value="recursive" />
              <el-option label="flat（扁平切片）" value="flat" />
            </el-select>
          </el-form-item>
          <el-form-item label="separators">
            <el-input v-model="customChunk.separatorsStr" placeholder="\n\n,\n, （逗号分隔）" />
            <span class="form-hint">分隔符列表，逗号分隔</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" @click="saveCustomChunk">保存自定义模板</el-button>
          </el-form-item>
        </template>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getConfig, saveConfig as saveConfigApi } from '../api'
import { ElMessage } from 'element-plus'

const config = ref({
  EMBEDDING_API_URL: 'http://127.0.0.1:5000/v1/embeddings',
  EMBEDDING_API_KEY: '',
  EMBEDDING_MODEL: 'text-embedding-qwen3-embedding-4b',
  EMBEDDING_DIM: 2560,
  RERANK_ENABLED: true,
  RERANK_API_URL: 'http://127.0.0.1:5001',
  RERANK_API_KEY: '',
  RERANK_MODEL: '',
  CHROMA_SERVER_HOST: '127.0.0.1',
  CHROMA_SERVER_PORT: 9898,
  MCP_SERVER_HOST: '127.0.0.1',
  MCP_SERVER_PORT: 9766,
  CHUNK_TEMPLATE: 'academic'
})

const loading = ref(false)

const customChunk = ref({
  chunk_size: 1000,
  overlap: 100,
  strategy: 'recursive',
  separatorsStr: '\\n\\n,\\n, ,'
})

const loadConfig = async () => {
  loading.value = true
  try {
    const response = await getConfig()
    if (response.status === 'success') {
      const env = response.data.env || {}
      config.value = {
        EMBEDDING_API_URL: env.EMBEDDING_API_URL || config.value.EMBEDDING_API_URL,
        EMBEDDING_API_KEY: env.EMBEDDING_API_KEY || '',
        EMBEDDING_MODEL: env.EMBEDDING_MODEL || config.value.EMBEDDING_MODEL,
        EMBEDDING_DIM: parseInt(env.EMBEDDING_DIM) || config.value.EMBEDDING_DIM,
        RERANK_ENABLED: env.RERANK_ENABLED === 'true',
        RERANK_API_URL: env.RERANK_API_URL || config.value.RERANK_API_URL,
        RERANK_API_KEY: env.RERANK_API_KEY || '',
        RERANK_MODEL: env.RERANK_MODEL || '',
        CHROMA_SERVER_HOST: env.CHROMA_SERVER_HOST || config.value.CHROMA_SERVER_HOST,
        CHROMA_SERVER_PORT: parseInt(env.CHROMA_SERVER_PORT) || config.value.CHROMA_SERVER_PORT,
        MCP_SERVER_HOST: env.MCP_SERVER_HOST || config.value.MCP_SERVER_HOST,
        MCP_SERVER_PORT: parseInt(env.MCP_SERVER_PORT) || config.value.MCP_SERVER_PORT,
        CHUNK_TEMPLATE: env.CHUNK_TEMPLATE || config.value.CHUNK_TEMPLATE,
      }
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  loading.value = true
  try {
    const env = {
      EMBEDDING_API_URL: config.value.EMBEDDING_API_URL,
      EMBEDDING_API_KEY: config.value.EMBEDDING_API_KEY,
      EMBEDDING_MODEL: config.value.EMBEDDING_MODEL,
      EMBEDDING_DIM: String(config.value.EMBEDDING_DIM),
      RERANK_ENABLED: String(config.value.RERANK_ENABLED),
      RERANK_API_URL: config.value.RERANK_API_URL,
      RERANK_API_KEY: config.value.RERANK_API_KEY,
      RERANK_MODEL: config.value.RERANK_MODEL,
      CHROMA_SERVER_HOST: config.value.CHROMA_SERVER_HOST,
      CHROMA_SERVER_PORT: String(config.value.CHROMA_SERVER_PORT),
      MCP_SERVER_HOST: config.value.MCP_SERVER_HOST,
      MCP_SERVER_PORT: String(config.value.MCP_SERVER_PORT),
      CHUNK_TEMPLATE: config.value.CHUNK_TEMPLATE,
    }
    const response = await saveConfigApi({ env })
    if (response.status === 'success') {
      ElMessage.success('配置保存成功')
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadConfig)

const saveCustomChunk = async () => {
  loading.value = true
  try {
    const seps = customChunk.value.separatorsStr.split(',').map(s => {
      s = s.trim()
      return s.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\t/g, '\t')
    })
    const cfg = {
      env: {
        EMBEDDING_API_URL: config.value.EMBEDDING_API_URL,
        EMBEDDING_API_KEY: config.value.EMBEDDING_API_KEY,
        EMBEDDING_MODEL: config.value.EMBEDDING_MODEL,
        EMBEDDING_DIM: String(config.value.EMBEDDING_DIM),
        RERANK_ENABLED: String(config.value.RERANK_ENABLED),
        RERANK_API_URL: config.value.RERANK_API_URL,
        RERANK_API_KEY: config.value.RERANK_API_KEY,
        RERANK_MODEL: config.value.RERANK_MODEL,
        CHROMA_SERVER_HOST: config.value.CHROMA_SERVER_HOST,
        CHROMA_SERVER_PORT: String(config.value.CHROMA_SERVER_PORT),
        MCP_SERVER_HOST: config.value.MCP_SERVER_HOST,
        MCP_SERVER_PORT: String(config.value.MCP_SERVER_PORT),
        CHUNK_TEMPLATE: 'custom',
      },
      config: {
        chunk: {
          templates: {
            custom: {
              name: '自定义模板',
              chunk_size: customChunk.value.chunk_size,
              overlap: customChunk.value.overlap,
              strategy: customChunk.value.strategy,
              separators: seps
            }
          }
        }
      }
    }
    const response = await saveConfigApi(cfg)
    if (response.status === 'success') {
      ElMessage.success('自定义模板已保存')
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}
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

.form-hint {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>

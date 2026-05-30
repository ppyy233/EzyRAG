<template>
  <div class="config-page">
    <div class="page-header">
      <h2>配置管理</h2>
      <p>管理系统配置参数</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 环境配置 -->
      <el-tab-pane label="环境配置" name="env">
        <div class="config-section">
          <h3>Embedding 配置</h3>
          <el-form label-width="140px">
            <el-form-item label="模式">
              <el-radio-group v-model="config.embedding_mode">
                <el-radio value="cloud">云端</el-radio>
                <el-radio value="local">本地</el-radio>
              </el-radio-group>
            </el-form-item>

            <template v-if="config.embedding_mode === 'cloud'">
              <el-form-item label="云端 URL">
                <el-input v-model="config.embedding_cloud_url" placeholder="https://api.siliconflow.cn/v1/embeddings" />
              </el-form-item>
              <el-form-item label="API Key">
                <el-input v-model="config.embedding_cloud_api_key" type="password" show-password placeholder="可选" />
              </el-form-item>
              <el-form-item label="模型名称">
                <el-input v-model="config.embedding_cloud_model" placeholder="BAAI/bge-m3" />
              </el-form-item>
              <el-form-item label="向量维度">
                <el-input v-model="config.embedding_cloud_dim" placeholder="留空自动检测" />
              </el-form-item>
            </template>

            <template v-else>
              <el-form-item label="本地 URL">
                <el-input v-model="config.embedding_local_url" placeholder="http://127.0.0.1:1234/v1/embeddings" />
              </el-form-item>
              <el-form-item label="模型路径">
                <el-input v-model="config.embedding_local_model_path" placeholder="data/models/embedding" />
              </el-form-item>
              <el-form-item label="向量维度">
                <el-input v-model="config.embedding_local_dim" placeholder="留空自动检测" />
              </el-form-item>
            </template>
          </el-form>
        </div>

        <el-divider />

        <div class="config-section">
          <h3>Rerank 配置</h3>
          <el-form label-width="140px">
            <el-form-item label="启用">
              <el-switch v-model="rerankEnabled" />
            </el-form-item>

            <template v-if="rerankEnabled">
              <el-form-item label="模式">
                <el-radio-group v-model="config.rerank_mode">
                  <el-radio value="cloud">云端</el-radio>
                  <el-radio value="local">本地</el-radio>
                </el-radio-group>
              </el-form-item>

              <template v-if="config.rerank_mode === 'cloud'">
                <el-form-item label="云端 URL">
                  <el-input v-model="config.rerank_cloud_url" placeholder="https://api.siliconflow.cn/v1/rerank" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="config.rerank_cloud_api_key" type="password" show-password placeholder="可选" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="config.rerank_cloud_model" placeholder="BAAI/bge-reranker-v2-m3" />
                </el-form-item>
              </template>

              <template v-else>
                <el-form-item label="本地 URL">
                  <el-input v-model="config.rerank_local_url" placeholder="http://127.0.0.1:5001" />
                </el-form-item>
                <el-form-item label="模型路径">
                  <el-input v-model="config.rerank_local_model_path" placeholder="data/models/rerank" />
                </el-form-item>
              </template>
            </template>
          </el-form>
        </div>

        <el-divider />

        <div class="config-section">
          <h3>服务配置</h3>
          <el-form label-width="140px">
            <el-form-item label="ChromaDB">
              <el-col :span="11">
                <el-input v-model="config.chroma_host" placeholder="127.0.0.1" />
              </el-col>
              <el-col :span="2" style="text-align: center;">:</el-col>
              <el-col :span="11">
                <el-input-number v-model="config.chroma_port" :min="1" :max="65535" style="width: 100%;" />
              </el-col>
            </el-form-item>
            <el-form-item label="MCP">
              <el-col :span="11">
                <el-input v-model="config.mcp_host" placeholder="127.0.0.1" />
              </el-col>
              <el-col :span="2" style="text-align: center;">:</el-col>
              <el-col :span="11">
                <el-input-number v-model="config.mcp_port" :min="1" :max="65535" style="width: 100%;" />
              </el-col>
            </el-form-item>
          </el-form>
        </div>

        <div class="config-actions">
          <el-button type="primary" @click="saveConfig" :loading="saving">
            <el-icon><Check /></el-icon>
            <span>保存环境配置</span>
          </el-button>
          <el-button @click="loadConfig">
            <el-icon><Refresh /></el-icon>
            <span>重新加载</span>
          </el-button>
        </div>
      </el-tab-pane>

      <!-- 切片配置 -->
      <el-tab-pane label="切片配置" name="chunk">
        <div class="config-section">
          <h3>切片配置</h3>
          <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
            当前使用的配置将用于文档切片。修改后点击"保存切片配置"立即生效，无需重启服务。
          </el-alert>

          <el-card class="chunk-card">
            <template #header>
              <div class="chunk-card-header">
                <span>选择模板</span>
                <el-tag v-if="isCustomTemplate" type="warning">自定义</el-tag>
                <el-tag v-else type="success">预设</el-tag>
              </div>
            </template>
            
            <el-form label-width="120px">
              <el-form-item label="模板">
                <el-select v-model="selectedTemplate" @change="handleTemplateChange" style="width: 100%;">
                  <el-option
                    v-for="(template, key) in templates"
                    :key="key"
                    :label="`${template.name} (${key})`"
                    :value="key"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card class="chunk-card" style="margin-top: 16px;">
            <template #header>
              <div class="chunk-card-header">
                <span>切片参数</span>
                <el-button size="small" @click="resetChunkConfig">重置为模板默认值</el-button>
              </div>
            </template>
            
            <el-form label-width="120px">
              <el-form-item label="chunk_size">
                <el-input-number v-model="chunkConfig.chunk_size" :min="100" :max="10000" :step="100" style="width: 200px;" />
                <span class="form-hint">每个切片的最大字符数</span>
              </el-form-item>

              <el-form-item label="overlap">
                <el-input-number v-model="chunkConfig.overlap" :min="0" :max="1000" :step="10" style="width: 200px;" />
                <span class="form-hint">切片之间的重叠字符数</span>
              </el-form-item>

              <el-form-item label="strategy">
                <el-select v-model="chunkConfig.strategy" style="width: 200px;">
                  <el-option label="递归切分 (recursive)" value="recursive" />
                  <el-option label="扁平切分 (flat)" value="flat" />
                </el-select>
                <span class="form-hint">递归适合文档，扁平适合代码</span>
              </el-form-item>
            </el-form>
          </el-card>
        </div>

        <div class="config-actions">
          <el-button type="primary" @click="saveChunkConfig" :loading="savingChunk">
            <el-icon><Check /></el-icon>
            <span>保存切片配置</span>
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { configApi } from '../api'
import { ElMessage } from 'element-plus'
import { Check, Refresh } from '@element-plus/icons-vue'

const activeTab = ref('env')
const saving = ref(false)
const savingChunk = ref(false)
const rerankEnabled = ref(true)
const templates = ref({})

const config = ref({
  embedding_mode: 'cloud',
  embedding_cloud_url: '',
  embedding_cloud_api_key: '',
  embedding_cloud_model: '',
  embedding_cloud_dim: '',
  embedding_local_url: '',
  embedding_local_model_path: '',
  embedding_local_dim: '',
  rerank_mode: 'local',
  rerank_cloud_url: '',
  rerank_cloud_api_key: '',
  rerank_cloud_model: '',
  rerank_local_url: '',
  rerank_local_model_path: '',
  chroma_host: '127.0.0.1',
  chroma_port: 9898,
  mcp_host: '127.0.0.1',
  mcp_port: 9766
})

const selectedTemplate = ref('academic')
const chunkConfig = ref({
  chunk_size: 2000,
  overlap: 200,
  strategy: 'recursive'
})

// 判断是否为自定义模板
const isCustomTemplate = computed(() => {
  return selectedTemplate.value === 'custom' || 
    !Object.keys(templates.value).includes(selectedTemplate.value)
})

const handleTemplateChange = (templateKey) => {
  const template = templates.value[templateKey]
  if (template) {
    chunkConfig.value = {
      chunk_size: template.chunk_size,
      overlap: template.overlap,
      strategy: template.strategy
    }
  }
}

const resetChunkConfig = () => {
  const template = templates.value[selectedTemplate.value]
  if (template) {
    chunkConfig.value = {
      chunk_size: template.chunk_size,
      overlap: template.overlap,
      strategy: template.strategy
    }
    ElMessage.success(`已重置为 ${template.name} 的默认值`)
  }
}

const loadConfig = async () => {
  try {
    const response = await configApi.get()
    if (response.status === 'success') {
      const env = response.data.env || {}
      templates.value = response.data.templates || {}
      
      config.value = {
        embedding_mode: env.EMBEDDING_MODE || 'cloud',
        embedding_cloud_url: env.EMBEDDING_CLOUD_URL || '',
        embedding_cloud_api_key: env.EMBEDDING_CLOUD_API_KEY || '',
        embedding_cloud_model: env.EMBEDDING_CLOUD_MODEL || '',
        embedding_cloud_dim: env.EMBEDDING_CLOUD_DIM || '',
        embedding_local_url: env.EMBEDDING_LOCAL_URL || '',
        embedding_local_model_path: env.EMBEDDING_LOCAL_MODEL_PATH || '',
        embedding_local_dim: env.EMBEDDING_LOCAL_DIM || '',
        rerank_mode: env.RERANK_MODE || 'local',
        rerank_cloud_url: env.RERANK_CLOUD_URL || '',
        rerank_cloud_api_key: env.RERANK_CLOUD_API_KEY || '',
        rerank_cloud_model: env.RERANK_CLOUD_MODEL || '',
        rerank_local_url: env.RERANK_LOCAL_URL || '',
        rerank_local_model_path: env.RERANK_LOCAL_MODEL_PATH || '',
        chroma_host: env.CHROMA_SERVER_HOST || '127.0.0.1',
        chroma_port: parseInt(env.CHROMA_SERVER_PORT) || 9898,
        mcp_host: env.MCP_SERVER_HOST || '127.0.0.1',
        mcp_port: parseInt(env.MCP_SERVER_PORT) || 9766
      }
      
      rerankEnabled.value = env.RERANK_ENABLED !== 'false'
      selectedTemplate.value = env.CHUNK_TEMPLATE || 'academic'
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

const loadChunkConfig = async () => {
  try {
    const response = await configApi.getChunk()
    if (response.status === 'success') {
      const current = response.data.current
      templates.value = response.data.templates
      
      // 尝试匹配模板
      let matched = false
      for (const [key, template] of Object.entries(templates.value)) {
        if (template.chunk_size === current.chunk_size && 
            template.overlap === current.overlap && 
            template.strategy === current.strategy) {
          selectedTemplate.value = key
          matched = true
          break
        }
      }
      
      // 如果没有匹配到模板，设置为 custom
      if (!matched) {
        selectedTemplate.value = 'custom'
      }
      
      chunkConfig.value = {
        chunk_size: current.chunk_size,
        overlap: current.overlap,
        strategy: current.strategy
      }
    }
  } catch (error) {
    console.error('加载切片配置失败:', error)
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const data = {
      embedding_mode: config.value.embedding_mode,
      embedding_cloud_url: config.value.embedding_cloud_url,
      embedding_cloud_api_key: config.value.embedding_cloud_api_key,
      embedding_cloud_model: config.value.embedding_cloud_model,
      embedding_cloud_dim: config.value.embedding_cloud_dim,
      embedding_local_url: config.value.embedding_local_url,
      embedding_local_model_path: config.value.embedding_local_model_path,
      embedding_local_dim: config.value.embedding_local_dim,
      rerank_enabled: rerankEnabled.value ? 'true' : 'false',
      rerank_mode: config.value.rerank_mode,
      rerank_cloud_url: config.value.rerank_cloud_url,
      rerank_cloud_api_key: config.value.rerank_cloud_api_key,
      rerank_cloud_model: config.value.rerank_cloud_model,
      rerank_local_url: config.value.rerank_local_url,
      rerank_local_model_path: config.value.rerank_local_model_path,
      chroma_host: config.value.chroma_host,
      chroma_port: String(config.value.chroma_port),
      mcp_host: config.value.mcp_host,
      mcp_port: String(config.value.mcp_port),
      chunk_template: selectedTemplate.value
    }
    
    await configApi.update(data)
    ElMessage.success('环境配置已保存，部分配置需要重启服务生效')
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const saveChunkConfig = async () => {
  savingChunk.value = true
  try {
    await configApi.updateChunk({
      chunk_size: chunkConfig.value.chunk_size,
      overlap: chunkConfig.value.overlap,
      strategy: chunkConfig.value.strategy
    })
    ElMessage.success('切片配置已保存，下次同步/重建将使用新配置')
  } catch (error) {
    console.error('保存切片配置失败:', error)
    ElMessage.error('保存切片配置失败')
  } finally {
    savingChunk.value = false
  }
}

onMounted(() => {
  loadConfig()
  loadChunkConfig()
})
</script>

<style scoped>
.config-page {
  max-width: 1000px;
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

.config-section {
  padding: 20px;
}

.config-section h3 {
  margin-bottom: 20px;
  color: #303133;
  font-size: 18px;
}

.config-actions {
  margin-top: 20px;
  padding: 20px;
  display: flex;
  gap: 12px;
}

.chunk-card {
  margin-bottom: 16px;
}

.chunk-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-hint {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}
</style>

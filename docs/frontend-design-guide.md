# Ezy-RAG 前端设计与交互经验总结

## 1. 项目技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue.js | 3.4+ |
| 构建工具 | Vite | 5.0+ |
| UI 组件库 | Element Plus | 2.5+ |
| HTTP 客户端 | Axios | 1.6+ |
| 路由 | Vue Router | 4.2+ |

---

## 2. 架构设计经验

### 2.1 前后端分离 + 生产模式合并

**开发模式**：Vite dev server (5173) + API server (9767)，通过 proxy 转发 `/api` 请求

**生产模式**：API server 直接托管 `frontend/dist/` 静态文件，无需单独的前端服务器

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': { target: 'http://127.0.0.1:9767', changeOrigin: true },
    '/ws':  { target: 'ws://127.0.0.1:9767', ws: true }
  }
}
```

**经验**：生产环境只需启动一个 API server，前端和后端共用同一个端口，简化部署。

### 2.2 SPA 路由 fallback

Vue Router 使用 `createWebHistory()`，刷新非根路径时会 404。必须在后端添加 fallback：

```python
# servers/api.py
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    file_path = frontend_dist / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(frontend_dist / "index.html"))
```

**经验**：所有非 API、非静态资源的路由都返回 `index.html`，让前端路由处理。

### 2.3 静态资源挂载路径

Vite 构建产物在 `dist/assets/` 目录，必须挂载到 `/assets` 而非 `/static`：

```python
app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
```

**经验**：挂载路径必须与 HTML 中引用的路径一致，否则 JS/CSS 加载失败导致白屏。

---

## 3. 组件设计经验

### 3.1 页面结构

| 页面 | 功能 | 关键组件 |
|------|------|----------|
| Home.vue | 状态仪表盘 | 统计卡片、服务状态、快速操作 |
| Documents.vue | 文档管理 | 双 Tab、分页、上传、进度日志 |
| Search.vue | 知识库搜索 | 搜索框、结果列表、相似度标签 |
| Config.vue | 配置管理 | 表单、条件展开区域 |
| Services.vue | 服务管理 | 状态表格、启动进度条 |

### 3.2 导航栏设计

```vue
<el-menu mode="horizontal" router>
  <el-menu-item index="/">首页</el-menu-item>
  <el-menu-item index="/documents">文档管理</el-menu-item>
  <el-menu-item index="/search">搜索</el-menu-item>
  <el-menu-item index="/config">配置</el-menu-item>
  <el-menu-item index="/services">服务</el-menu-item>
</el-menu>
```

**经验**：所有页面都是一级菜单项，不要用二级菜单（`el-sub-menu`），用户操作路径越短越好。

### 3.3 双 Tab 设计（文档管理）

将「本地文件」和「向量库文档」分为两个独立 Tab：

```vue
<el-tabs v-model="activeTab" type="border-card">
  <el-tab-pane label="本地文件" name="local">
    <!-- 上传、导入、文件列表 -->
  </el-tab-pane>
  <el-tab-pane label="向量库文档" name="vector">
    <!-- 查看、删除、向量库列表 -->
  </el-tab-pane>
</el-tabs>
```

**经验**：当两个数据源有关联但操作逻辑不同时，用 Tab 分离比混在一个列表更清晰。

---

## 4. 交互设计经验

### 4.1 操作反馈三要素

任何异步操作都需要：

1. **Loading 状态** — 按钮显示加载动画
2. **进度提示** — 显示当前处理进度（百分比/文件名）
3. **结果反馈** — 成功/失败的明确提示

```vue
<el-button :loading="importingLock" @click="importAll">导入全部</el-button>
<el-progress :percentage="progress.percent" />
<el-message :type="success ? 'success' : 'error'" />
```

### 4.2 并发锁机制

防止用户同时触发多个相同操作：

```javascript
const importingLock = ref(false)

const importAll = async () => {
  if (importingLock.value) {
    ElMessage.warning('正在导入中，请等待完成或点击停止')
    return
  }
  importingLock.value = true
  // ... 执行操作
  importingLock.value = false
}
```

**经验**：用布尔锁 + 提示比直接禁用按钮更好，用户知道发生了什么。

### 4.3 停止/取消机制

长时间操作必须提供停止按钮：

```vue
<el-button v-if="importingLock" type="danger" @click="stopVectorization">
  停止向量化
</el-button>
```

**经验**：停止不是即时生效的，需要：
1. 前端设置取消标志
2. 调用后端取消 API
3. 后端清空队列 + 设置取消标志
4. 当前正在运行的任务完成后检查标志，丢弃结果
5. 前端跳出循环

### 4.4 日志窗口

长时间操作需要显示详细日志：

```vue
<div class="log-window">
  <div v-for="log in logs" class="log-line">
    <span class="log-time">{{ log.time }}</span>
    <span class="log-msg">{{ log.message }}</span>
  </div>
</div>
```

```css
.log-window {
  background: #1e1e1e;  /* 深色终端风格 */
  color: #d4d4d4;
  font-family: 'Consolas', monospace;
  max-height: 300px;
  overflow-y: auto;
}
```

**经验**：日志窗口用深色终端风格，让用户感觉在看真正的命令行输出。自动滚动到底部。

### 4.5 确认对话框

危险操作必须二次确认：

```javascript
await ElMessageBox.confirm('确定要删除吗？', '确认', { type: 'warning' })
```

**经验**：`type: 'warning'` 用于危险操作，`type: 'info'` 用于普通确认。

### 4.6 分页设计

数据量大时使用前端分页：

```vue
<el-table :data="pagedData" />
<el-pagination
  v-model:current-page="currentPage"
  :page-size="pageSize"
  :total="totalCount"
  layout="total, prev, pager, next"
/>
```

```javascript
const pagedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return allData.value.slice(start, start + pageSize)
})
```

**经验**：数据量 < 1000 时用前端分页即可，数据量大时用后端分页。

---

## 5. API 设计经验

### 5.1 统一响应格式

```python
class ApiResponse(BaseModel):
    status: str      # "success" 或 "error"
    data: Any = None
    message: str = ""
```

**经验**：前端只需检查 `response.status === 'success'`，统一处理错误。

### 5.2 Axios 拦截器

```javascript
api.interceptors.response.use(
  response => response.data,  // 直接返回 data，省去 .data 链
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)
```

**经验**：拦截器自动解包响应，前端调用时直接 `const result = await api.get(...)`。

### 5.3 WebSocket 实时推送

用于进度更新、状态变更等场景：

```python
# 后端广播
await manager.broadcast({
    "type": "vectorize",
    "data": {"file": "doc.txt", "percent": 50, "message": "进度: 50/100"},
    "timestamp": datetime.now().isoformat()
})
```

```javascript
// 前端监听
ws.value.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'vectorize') {
    updateProgress(data.data)
  }
}
```

**经验**：用 `type` 字段区分消息类型，前端根据类型分发处理。

---

## 6. 样式设计经验

### 6.1 颜色系统

| 用途 | Element Plus 类型 |
|------|-------------------|
| 主要操作 | `type="primary"` (蓝色) |
| 成功状态 | `type="success"` (绿色) |
| 警告操作 | `type="warning"` (橙色) |
| 危险操作 | `type="danger"` (红色) |
| 信息提示 | `type="info"` (灰色) |

### 6.2 布局原则

```css
.container {
  max-width: 1200px;
  margin: 0 auto;      /* 居中 */
  padding: 20px;        /* 内边距 */
}

.card {
  margin-bottom: 20px;  /* 卡片间距 */
}
```

**经验**：固定最大宽度 + 居中，在大屏和小屏上都有良好的阅读体验。

### 6.3 表格设计

```vue
<el-table :data="data" stripe>           <!-- 斑马纹 -->
  <el-table-column type="selection" />   <!-- 复选框 -->
  <el-table-column prop="name" label="名称" min-width="200" />
  <el-table-column label="状态" width="120">
    <template #default="scope">
      <el-tag :type="scope.row.online ? 'success' : 'danger'">
        {{ scope.row.online ? '在线' : '离线' }}
      </el-tag>
    </template>
  </el-table-column>
</el-table>
```

**经验**：
- `stripe` 斑马纹提高可读性
- `min-width` 用于自适应列，`width` 用于固定列
- 状态列用 `el-tag` 而非纯文本

---

## 7. 常见坑与解决方案

### 7.1 变量名冲突

```javascript
// 错误：函数名和 ref 同名
const uploadFiles = ref([])
const uploadFiles = async () => {
  for (const file of uploadFiles.value) { ... }  // 报错！
}

// 正确：使用不同名称
const uploadFileList = ref([])
const uploadFiles = async () => {
  for (const file of uploadFileList.value) { ... }
}
```

### 7.2 el-upload 的 on-change 行为

`el-upload` 的 `on-change` 在每次选择文件时触发，如果用户多次选择，文件会累加。

**解决**：手动管理文件列表，清空 input 的 value。

### 7.3 浏览器缓存

修改代码后前端不更新？可能是浏览器缓存了旧的 JS/CSS。

**解决**：`npm run build` 重新构建，或浏览器强制刷新 (Ctrl+Shift+R)。

### 7.4 中文路径编码

Windows 中文路径在 API 响应中可能显示为乱码，但不影响功能。

**解决**：前端显示时使用 `filename` 字段而非完整 `source` 路径。

---

## 8. 性能优化

### 8.1 懒加载路由

```javascript
const routes = [
  { path: '/documents', component: () => import('../views/Documents.vue') }
]
```

**经验**：首屏只加载当前页面的代码，其他页面按需加载。

### 8.2 防抖搜索

搜索输入框应添加防抖，避免每次按键都发请求：

```javascript
let timer = null
const onInput = (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => search(value), 300)
}
```

### 8.3 批量操作优化

批量导入时，逐个发送请求比一次性发送更安全：
- 可以显示每个文件的进度
- 单个失败不影响其他文件
- 可以随时停止

---

## 9. 总结

| 原则 | 说明 |
|------|------|
| 即时反馈 | 每个操作都要有 loading、进度、结果提示 |
| 可中断 | 长时间操作必须提供停止按钮 |
| 并发保护 | 用锁机制防止重复触发 |
| 日志透明 | 显示详细的操作日志，用户知道发生了什么 |
| 路径简洁 | 一级菜单，最少点击次数到达目标 |
| 错误友好 | 明确的错误信息，不是 "操作失败" |
| 状态可见 | 服务状态、连接状态、数据状态一目了然 |

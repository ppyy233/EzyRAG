<template>
  <div class="navbar">
    <div class="navbar-brand">
      <el-icon :size="24"><DataBoard /></el-icon>
      <span>Ezy-RAG</span>
      <span class="version">v1.0.0</span>
    </div>
    <div class="navbar-menu">
      <router-link to="/" class="nav-item" :class="{ active: activeIndex === '/' }">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </router-link>
      <router-link to="/documents" class="nav-item" :class="{ active: activeIndex === '/documents' }">
        <el-icon><Document /></el-icon>
        <span>文档管理</span>
      </router-link>
      <router-link to="/search" class="nav-item" :class="{ active: activeIndex === '/search' }">
        <el-icon><Search /></el-icon>
        <span>搜索</span>
      </router-link>
      <router-link to="/config" class="nav-item" :class="{ active: activeIndex === '/config' }">
        <el-icon><Setting /></el-icon>
        <span>配置</span>
      </router-link>
      <router-link to="/services" class="nav-item" :class="{ active: activeIndex === '/services' }">
        <el-icon><Monitor /></el-icon>
        <span>服务</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeIndex = computed(() => route.path)
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: bold;
  color: #fff;
  flex-shrink: 0;
}

.version {
  font-size: 12px;
  color: #bfcbd9;
  font-weight: normal;
}

.navbar-menu {
  display: flex;
  align-items: center;
  gap: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  height: 60px;
  color: #bfcbd9;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.3s;
  cursor: pointer;
}

.nav-item:hover {
  color: #409eff;
  background-color: rgba(64, 158, 255, 0.1);
}

.nav-item.active {
  color: #ffd04b;
  background-color: rgba(255, 208, 75, 0.1);
}
</style>

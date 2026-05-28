<template>
  <div class="navbar">
    <div class="navbar-brand">
      <el-icon><DataBoard /></el-icon>
      <span>Ezy-RAG</span>
    </div>
    <el-menu
      :default-active="activeIndex"
      mode="horizontal"
      background-color="#545c64"
      text-color="#fff"
      active-text-color="#ffd04b"
      router
    >
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </el-menu-item>
      <el-menu-item index="/documents">
        <el-icon><Document /></el-icon>
        <span>文档管理</span>
      </el-menu-item>
      <el-menu-item index="/search">
        <el-icon><Search /></el-icon>
        <span>搜索</span>
      </el-menu-item>
      <el-menu-item index="/config">
        <el-icon><Setting /></el-icon>
        <span>配置</span>
      </el-menu-item>
      <el-menu-item index="/services">
        <el-icon><Monitor /></el-icon>
        <span>服务</span>
      </el-menu-item>
    </el-menu>
    <div class="navbar-status">
      <el-tag :type="isConnected ? 'success' : 'danger'" size="small">
        {{ isConnected ? '已连接' : '未连接' }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useWebSocket } from '../composables/useWebSocket'

const route = useRoute()
const activeIndex = computed(() => route.path)

const { isConnected } = useWebSocket(`ws://${window.location.host}/ws`)
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: bold;
  color: #fff;
}

.navbar-status {
  display: flex;
  align-items: center;
}
</style>

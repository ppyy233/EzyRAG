<template>
  <el-container class="app-container">
    <el-header>
      <Navbar />
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import Navbar from './components/Navbar.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}

.app-container {
  min-height: 100vh;
}

.el-header {
  background-color: #545c64;
  color: #fff;
  line-height: 60px;
  padding: 0 20px;
}

.el-main {
  background-color: #f5f5f5;
  padding: 20px;
}
</style>

<template>
  <div class="app-container">
    <el-container>
      <el-header>
        <el-menu mode="horizontal" router :default-active="$route.path">
          <el-menu-item index="/record">
            <el-icon><Camera /></el-icon>
            人脸采集
          </el-menu-item>
          <el-menu-item index="/manage">
            <el-icon><Management /></el-icon>
            数据管理
          </el-menu-item>
          <el-menu-item index="/recognition">
            <el-icon><Monitor /></el-icon>
            人脸识别
          </el-menu-item>
        </el-menu>
      </el-header>
      
      <el-main>
        <router-view v-slot="{ Component }">
          <component :is="Component" :key="$route.fullPath" />
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { Camera, Management, Monitor } from '@element-plus/icons-vue'
</script>

<style>
.app-container {
  height: 100%;
}

.el-container {
  height: 100%;
}

.el-header {
  padding: 0;
  border-bottom: 1px solid #eee;
}

.el-main {
  padding: 20px;
}
</style> 
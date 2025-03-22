<template>
  <div class="data-manage">
    <el-row :gutter="20">
      <!-- 左侧数据表格 -->
      <el-col :span="16">
        <el-card>
          <el-table :data="users" style="width: 100%">
            <el-table-column prop="stu_id" label="学号" width="120" />
            <el-table-column prop="face_id" label="Face ID" width="100" />
            <el-table-column prop="cn_name" label="姓名" width="120" />
            <el-table-column prop="en_name" label="汉语拼音" width="150" />
            <el-table-column prop="created_time" label="注册时间" width="180" />
          </el-table>
          <div class="tip-text">
            注：Face ID为 -1 说明该用户的人脸数据未被训练
          </div>
        </el-card>
      </el-col>

      <!-- 右侧功能区 -->
      <el-col :span="8">
        <!-- 数据库状态 -->
        <el-card class="mb-20">
          <template #header>
            <div class="card-header">
              <span>数据库状态</span>
            </div>
          </template>
          <el-button type="primary" @click="initDb" :icon="Refresh" class="mb-10" block>
            初始化数据库
          </el-button>
          <el-row>
            <el-col :span="16">
              <span>数据库已存人脸样本数：</span>
            </el-col>
            <el-col :span="8">
              <el-statistic :value="dbUserCount" />
            </el-col>
          </el-row>
        </el-card>

        <!-- 用户管理 -->
        <el-card class="mb-20">
          <template #header>
            <div class="card-header">
              <span>用户管理</span>
            </div>
          </template>
          <el-form :model="queryForm" label-width="80px">
            <el-form-item label="学号">
              <el-input v-model="queryForm.stu_id" placeholder="请输入学号" />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="queryForm.name" placeholder="请输入姓名" />
            </el-form-item>
          </el-form>
          <div class="button-group">
            <el-button type="primary" @click="queryUser" :icon="Search">查询用户</el-button>
            <el-button type="danger" @click="deleteUser" :icon="Delete">删除记录</el-button>
          </div>
        </el-card>

        <!-- 训练设置 -->
        <el-card class="mb-20">
          <template #header>
            <div class="card-header">
              <span>训练设置</span>
            </div>
          </template>
          <el-form-item label="图像预处理">
            <el-tooltip
              content="直方图均衡化可以提高图像对比度，减少光照影响，提升识别准确率"
              placement="top"
            >
              <div class="preprocessing-option">
                <el-checkbox v-model="isEqualizeHistEnabled">启用直方图均衡化</el-checkbox>
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </div>
            </el-tooltip>
          </el-form-item>
          <el-button 
            type="primary" 
            @click="trainModel" 
            :loading="isTraining"
            :icon="VideoPlay" 
            class="mt-10" 
            block
          >
            {{ isTraining ? '训练中...' : '训练人脸数据' }}
          </el-button>
        </el-card>

        <!-- 系统日志 -->
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统日志</span>
            </div>
          </template>
          <el-input
            type="textarea"
            v-model="logContent"
            :rows="8"
            readonly
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, Delete, VideoPlay, InfoFilled } from '@element-plus/icons-vue'
import axios from 'axios'

// 数据状态
const users = ref([])
const dbUserCount = ref(0)
const logContent = ref('')

// 查询表单
const queryForm = ref({
  stu_id: '',
  name: ''
})

// 训练设置
const isTraining = ref(false)
const isEqualizeHistEnabled = ref(false)

// 初始化数据库
const initDb = async () => {
  try {
    const response = await axios.post('/api/users/init_db/')
    await loadUsers()
    ElMessage.success('数据库初始化成功')
  } catch (error) {
    ElMessage.error('数据库初始化失败')
  }
}

// 加载用户列表
const loadUsers = async () => {
  try {
    const response = await axios.get('/api/users/')
    users.value = response.data
    dbUserCount.value = users.value.length
  } catch (error) {
    ElMessage.error('加载用户数据失败')
  }
}

// 查询用户
const queryUser = async () => {
  try {
    const response = await axios.get('/api/users/', {
      params: queryForm.value
    })
    users.value = response.data
    addLog('查询完成')
  } catch (error) {
    ElMessage.error('查询失败')
  }
}

// 删除用户
const deleteUser = async () => {
  if (!queryForm.value.stu_id) {
    ElMessage.warning('请输入要删除的学号')
    return
  }

  try {
    await ElMessageBox.confirm('确定要删除该用户吗？此操作不可恢复', '警告', {
      type: 'warning'
    })
    
    await axios.delete(`/api/users/${queryForm.value.stu_id}/`)
    await loadUsers()
    ElMessage.success('删除成功')
    addLog(`删除用户 ${queryForm.value.stu_id} 成功`)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 训练模型
const trainModel = async () => {
  try {
    isTraining.value = true
    addLog('开始训练模型...')
    
    const response = await axios.post('/api/users/train_model/', {
      equalize_hist: isEqualizeHistEnabled.value
    })
    
    if (response.data.success) {
      ElMessage.success('模型训练完成')
      addLog('人脸数据训练完成')
    } else {
      throw new Error(response.data.error)
    }
  } catch (error) {
    ElMessage.error(error.message || '模型训练失败')
    addLog(`训练失败: ${error.message}`)
  } finally {
    isTraining.value = false
  }
}

// 添加日志
const addLog = (message) => {
  const time = new Date().toLocaleString()
  logContent.value += `[${time}] ${message}\n`
}

// 页面加载时获取数据
onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.data-manage {
  padding: 20px;
}

.mb-20 {
  margin-bottom: 20px;
}

.mb-10 {
  margin-bottom: 10px;
}

.mt-10 {
  margin-top: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.button-group {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.tip-text {
  color: #666;
  font-size: 12px;
  margin-top: 10px;
  padding-left: 10px;
}

.preprocessing-option {
  display: flex;
  align-items: center;
  gap: 5px;
}

.info-icon {
  color: #909399;
  cursor: help;
}
</style> 
<template>
  <div class="data-record">
    <el-row :gutter="20">
      <!-- 左侧摄像头区域 -->
      <el-col :span="16">
        <el-card class="camera-card">
          <template #header>
            <div class="card-header">
              <span>人脸采集</span>
            </div>
          </template>
          
          <!-- 摄像头预览 -->
          <div class="camera-container">
            <div class="video-wrapper">
              <video 
                ref="video" 
                width="640" 
                height="480" 
                autoplay 
                :class="{ detecting: isFaceDetectEnabled }"
              ></video>
              <canvas 
                ref="canvas" 
                width="640" 
                height="480" 
                class="face-canvas"
              ></canvas>
            </div>
          </div>

          <!-- 控制按钮 -->
          <div class="camera-controls">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-checkbox v-model="useExternalCamera">使用外接摄像头</el-checkbox>
              </el-col>
              <el-col :span="12">
                <el-button 
                  type="primary" 
                  @click="toggleCamera"
                  :icon="cameraActive ? VideoPause : VideoPlay"
                >
                  {{ cameraActive ? '关闭摄像头' : '打开摄像头' }}
                </el-button>
              </el-col>
            </el-row>
          </div>

          <!-- 采集进度 -->
          <div class="record-progress">
            <el-row>
              <el-col :span="12">已采集帧数：</el-col>
              <el-col :span="12">
                <el-statistic :value="faceRecordCount" />
              </el-col>
            </el-row>
            <!-- 添加人脸采集按钮 -->
            <el-row class="mt-10">
              <el-col :span="24">
                <el-button 
                  type="primary" 
                  @click="startFaceRecord"
                  :disabled="!cameraActive || isRecording"
                  :loading="isRecording"
                  :icon="Camera"
                >
                  {{ isRecording ? '采集中...' : '开始采集人脸数据' }}
                </el-button>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧信息区域 -->
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

        <!-- 用户信息 -->
        <el-card class="mb-20">
          <template #header>
            <div class="card-header">
              <span>用户信息</span>
            </div>
          </template>
          <el-form :model="userForm" label-width="80px" :rules="rules" ref="userFormRef">
            <el-form-item label="学号" prop="stu_id">
              <el-input 
                v-model="userForm.stu_id" 
                maxlength="12"
                placeholder="请输入12位学号"
              />
            </el-form-item>
            <el-form-item label="姓名" prop="cn_name">
              <el-input 
                v-model="userForm.cn_name" 
                maxlength="10"
                placeholder="请输入姓名，10个汉字以内"
              />
            </el-form-item>
            <el-form-item label="拼音" prop="en_name">
              <el-input 
                v-model="userForm.en_name" 
                maxlength="16"
                placeholder="16个字母以内，包含空格"
              />
            </el-form-item>
          </el-form>
          <div class="button-group">
            <el-button 
              type="primary" 
              @click="addOrUpdateUserInfo"
              :disabled="!userInfoComplete"
              :icon="Check"
            >
              确认信息
            </el-button>
            <el-button
              type="primary"
              :disabled="!isFaceDataReady"
              @click="migrateToDb"
            >
              保存到数据库
            </el-button>
          </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  VideoPlay, VideoPause, View, Select, Camera, 
  Refresh, Check, Upload 
} from '@element-plus/icons-vue'
import axios from 'axios'

// 摄像头相关
const video = ref(null)
const canvas = ref(null)
const cameraActive = ref(false)
const useExternalCamera = ref(false)
const isFaceDetectEnabled = ref(false)
let stream = null

// 人脸采集相关
const ws = ref(null)
const isRecording = ref(false)
const faceRecordCount = ref(0)
const isFaceDataReady = ref(false)
const minFaceRecordCount = 20  // 修改为20，与后端保持一致
let recordTimer = null  // 添加 recordTimer 声明
let detectTimer = ref(null)  // 修改为 let

// 数据库状态
const dbUserCount = ref(0)

// 用户表单
const userFormRef = ref(null)
const userForm = ref({
  stu_id: '',
  cn_name: '',
  en_name: ''
})

// 表单验证规则
const rules = {
  stu_id: [
    { required: true, message: '请输入学号', trigger: 'blur' },
    { pattern: /^\d{12}$/, message: '请输入12位数字学号', trigger: 'blur' }
  ],
  cn_name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { pattern: /^[\u4e00-\u9fa5]{1,10}$/, message: '请输入1-10个汉字', trigger: 'blur' }
  ],
  en_name: [
    { required: true, message: '请输入拼音', trigger: 'blur' },
    { pattern: /^[A-Za-z\s]{1,16}$/, message: '请输入1-16个英文字母', trigger: 'blur' }
  ]
}

// 日志
const logContent = ref('')

// 计算属性
const userInfoComplete = computed(() => {
  return userForm.value.stu_id && userForm.value.cn_name && userForm.value.en_name
})

// 添加连接状态标志
const isConnecting = ref(false)

// 摄像头控制
const toggleCamera = async () => {
  if (cameraActive.value) {
    stopCamera()
  } else {
    await startCamera()
  }
}

const startCamera = async () => {
  try {
    const constraints = {
      video: {
        deviceId: useExternalCamera.value ? undefined : 'default'
      }
    }
    stream = await navigator.mediaDevices.getUserMedia(constraints)
    video.value.srcObject = stream
    cameraActive.value = true
    addLog('摄像头已开启')
  } catch (err) {
    ElMessage.error('无法访问摄像头')
    addLog('摄像头启动失败')
  }
}

const stopCamera = () => {
  // 先停止媒体流
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
  }
  
  // 安全地清理视频元素
  if (video.value) {
    video.value.srcObject = null
  }
  
  // 重置状态
  cameraActive.value = false
  isFaceDetectEnabled.value = false
  
  addLog('摄像头已关闭')
}

// 开始人脸采集
const startFaceRecord = async () => {
  if (!userFormRef.value) return
  
  try {
    await userFormRef.value.validate()
    
    // 确保 WebSocket 连接
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      await connectWebSocket()  // 等待连接建立
    }
    
    isRecording.value = true
    
    // 发送开始采集消息
    ws.value.send(JSON.stringify({
      type: 'start_record',
      stu_id: userForm.value.stu_id
    }))
    
    // 开始定时发送图像数据
    recordTimer = setInterval(() => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        const context = canvas.value.getContext('2d')
        context.drawImage(video.value, 0, 0, 640, 480)
        const imageData = canvas.value.toDataURL('image/jpeg', 0.8)
        
        console.log('Sending face data...')  // 添加日志
        ws.value.send(JSON.stringify({
          type: 'record_face',
          image: imageData
        }))
      } else {
        console.log('WebSocket not ready, state:', ws.value?.readyState)  // 添加日志
      }
    }, 200)
  } catch (error) {
    console.error('Error in startFaceRecord:', error)  // 添加错误日志
    ElMessage.error('请检查输入信息')
  }
}

// 修改 WebSocket 连接函数，返回 Promise
const connectWebSocket = () => {
  return new Promise((resolve, reject) => {
    if (ws.value?.readyState === WebSocket.OPEN) {
      resolve()
      return
    }
    
    if (isConnecting.value) {
      reject(new Error('WebSocket is connecting'))
      return
    }
    
    isConnecting.value = true
    const wsUrl = `ws://${window.location.hostname}:8000/ws/face_record/`
    
    try {
      ws.value = new WebSocket(wsUrl)
      
      ws.value.onopen = () => {
        console.log('WebSocket connected')
        isConnecting.value = false
        resolve()
      }
      
      ws.value.onmessage = (event) => {
        const data = JSON.parse(event.data)
        console.log('Received message:', data)
        
        if (data.error) {
          console.error(data.error)
          addLog(data.error)
          return
        }
        
        switch(data.type) {
          case 'face_detect':
            if (data.face_rect) {
              drawFaceRect(data.face_rect)
            }
            if (data.record_count !== undefined) {
              faceRecordCount.value = data.record_count
              addLog(`已采集 ${faceRecordCount.value} 帧`)
            }
            break
            
          case 'record_started':
            ElMessage.success(data.message)
            addLog(data.message)
            faceRecordCount.value = 0
            isFaceDataReady.value = false
            break
          
          case 'record_completed':
            ElMessage.success(data.message)
            addLog(data.message)
            stopFaceRecord()
            isFaceDataReady.value = true
            break
        }
      }
      
      ws.value.onerror = (error) => {
        console.error('WebSocket error:', error)
        ElMessage.error('WebSocket连接错误')
        isConnecting.value = false
        reject(error)
      }
      
      ws.value.onclose = () => {
        console.log('WebSocket connection closed')
        ws.value = null
        isConnecting.value = false
        
        // 如果正在录制，尝试重连
        if (isRecording.value) {
          setTimeout(() => connectWebSocket(), 3000)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      isConnecting.value = false
      ElMessage.error('无法创建WebSocket连接')
      reject(error)
    }
  })
}

// 绘制人脸框
const drawFaceRect = (rect) => {
  if (!rect) return
  
  const context = canvas.value.getContext('2d')
  context.clearRect(0, 0, canvas.value.width, canvas.value.height)
  context.strokeStyle = '#67C23A'
  context.lineWidth = 2
  context.strokeRect(rect.x, rect.y, rect.width, rect.height)
}

// 停止人脸采集
const stopFaceRecord = () => {
  isRecording.value = false
  if (recordTimer) {
    clearInterval(recordTimer)
    recordTimer = null
  }
  // 清除人脸框 - 添加判断
  if (canvas.value) {  // 确保 canvas 存在
    const context = canvas.value.getContext('2d')
    context.clearRect(0, 0, canvas.value.width, canvas.value.height)
  }
}

// 初始化数据库
const initDb = async () => {
  try {
    await axios.post('/api/users/init_db/')
    await loadDbCount()
    ElMessage.success('数据库初始化成功')
    addLog('数据库初始化成功')
  } catch (error) {
    ElMessage.error('数据库初始化失败')
    addLog('数据库初始化失败')
  }
}

// 加载数据库计数
const loadDbCount = async () => {
  try {
    const response = await axios.get('/api/users/')
    dbUserCount.value = response.data.length
  } catch (error) {
    ElMessage.error('获取数据库信息失败')
  }
}

// 确认用户信息
const addOrUpdateUserInfo = async () => {
  if (!userFormRef.value) return
  
  try {
    await userFormRef.value.validate()
    ElMessage.success('用户信息已确认')
    addLog('用户信息已确认')
  } catch (error) {
    ElMessage.error('请检查输入信息')
  }
}

// 保存到数据库
const migrateToDb = async () => {
  if (!isFaceDataReady.value) {
    ElMessage.warning('请先完成人脸采集')
    return
  }

  try {
    console.log('Saving user info:', userForm.value)
    const response = await axios.post('/api/users/', userForm.value)
    console.log('Save response:', response.data)
    
    ElMessage.success('保存成功')
    addLog('用户信息已保存到数据库')
    await loadDbCount()
    
    // 先停止所有活动
    if (isRecording.value) {
      stopFaceRecord()
    }
    stopCamera()
    
    // 重置所有状态
    userForm.value = {
      stu_id: '',
      cn_name: '',
      en_name: ''
    }
    isFaceDataReady.value = false
    faceRecordCount.value = 0
    
  } catch (error) {
    console.error('Save error:', error)
    ElMessage.error(error.response?.data?.error || '保存失败')
    addLog(`保存失败: ${error.response?.data?.error || error.message}`)
  }
}

// 添加日志
const addLog = (message) => {
  const time = new Date().toLocaleString()
  logContent.value += `[${time}] ${message}\n`
}

// 生命周期钩子
onMounted(() => {
  loadDbCount()
})

onUnmounted(() => {
  // 先停止录制
  if (isRecording.value) {
    stopFaceRecord()
  }
  
  // 清理 WebSocket
  if (ws.value) {
    try {
      ws.value.close()
    } catch (error) {
      console.error('Error closing WebSocket:', error)
    }
    ws.value = null
  }
  
  // 最后停止摄像头
  stopCamera()
})
</script>

<style scoped>
.data-record {
  padding: 20px;
}

.camera-card {
  margin-bottom: 20px;
}

.camera-container {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.video-wrapper {
  position: relative;
  width: 640px;
  height: 480px;
}

.video-wrapper video,
.video-wrapper canvas {
  position: absolute;
  top: 0;
  left: 0;
}

.face-canvas {
  z-index: 1;
}

.camera-controls {
  margin: 20px 0;
}

.record-progress {
  margin-top: 20px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.mb-20 {
  margin-bottom: 20px;
}

.mb-10 {
  margin-bottom: 10px;
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

.mt-10 {
  margin-top: 10px;
}
</style>

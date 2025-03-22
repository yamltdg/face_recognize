<template>
  <div class="face-recognition">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="camera-card">
          <template #header>
            <div class="card-header">
              <span>实时识别</span>
              <el-switch
                v-model="isRecognizing"
                @change="toggleRecognition"
                :loading="loading"
              />
            </div>
          </template>
          
          <div class="camera-container">
            <div class="video-wrapper">
              <video 
                ref="video" 
                width="640" 
                height="480" 
                autoplay
                :class="{ recognizing: isRecognizing }"
              ></video>
              <canvas 
                ref="overlayCanvas" 
                width="640" 
                height="480" 
                class="face-overlay"
              ></canvas>
            </div>
            <canvas ref="canvas" width="640" height="480" style="display:none"></canvas>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="settings-card">
          <template #header>
            <div class="card-header">
              <span>识别设置</span>
            </div>
          </template>
          
          <el-form label-position="top">
            <el-form-item label="置信度阈值">
              <el-slider
                v-model="confidenceThreshold"
                :min="0"
                :max="100"
                :step="1"
              />
            </el-form-item>
            
            <el-form-item label="识别频率(ms)">
              <el-input-number
                v-model="recognitionInterval"
                :min="30"
                :max="1000"
                :step="10"
              />
            </el-form-item>
            
            <el-form-item label="检测方式">
              <el-radio-group v-model="detectionMethod">
                <el-tooltip content="OpenCV 速度快，适合普通场景" placement="top">
                  <el-radio label="opencv">OpenCV</el-radio>
                </el-tooltip>
                <el-tooltip content="Dlib 精度高，支持更多角度" placement="top">
                  <el-radio label="dlib">Dlib</el-radio>
                </el-tooltip>
              </el-radio-group>
            </el-form-item>
            
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
          </el-form>
        </el-card>
        
        <el-card class="log-card">
          <template #header>
            <div class="card-header">
              <span>识别日志</span>
              <el-button text @click="clearLogs">清空</el-button>
            </div>
          </template>
          
          <div class="log-container">
            <div v-for="(log, index) in recognitionLogs" :key="index" class="log-item">
              <span class="time">{{ log.time }}</span>
              <span :class="['status', log.status]">{{ log.message }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'

const video = ref(null)
const canvas = ref(null)
const overlayCanvas = ref(null)
const isRecognizing = ref(false)
const loading = ref(false)
const confidenceThreshold = ref(50)
const recognitionInterval = ref(350)
const recognitionLogs = ref([])

let recognitionTimer = null
let stream = null
const ws = ref(null)

let lastUpdateTime = 0
const minUpdateInterval = 30  // 最小更新间隔(ms)

// 添加连接状态标志
const isConnecting = ref(false)

// 添加直方图均衡化状态
const isEqualizeHistEnabled = ref(false)

// 添加检测方法状态
const detectionMethod = ref('opencv')

const startCamera = async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true })
    video.value.srcObject = stream
  } catch (err) {
    ElMessage.error('无法访问摄像头')
  }
}

const stopCamera = () => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
  }
}

const toggleRecognition = async (value) => {
  if (value) {
    if (!stream) await startCamera()
    startRecognition()
  } else {
    stopRecognition()
  }
}

const drawRecognitionResult = (data) => {
  const ctx = overlayCanvas.value.getContext('2d')
  ctx.clearRect(0, 0, 640, 480)
  
  if (data.face_rect) {
    const { x, y, width, height } = data.face_rect
    
    // 绘制人脸框
    ctx.strokeStyle = data.stu_id ? '#67C23A' : '#FF0000'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, width, height)
    
    // 如果是dlib检测且有关键点，绘制关键点和连线
    if (data.detection_method === 'dlib' && data.landmarks) {
      // 绘制关键点
      ctx.fillStyle = '#00FF00'
      
      // 定义不同部位的关键点索引
      const faceRegions = {
        jaw: [0, 16],
        rightBrow: [17, 21],
        leftBrow: [22, 26],
        nose: [27, 35],
        rightEye: [36, 41],
        leftEye: [42, 47],
        mouth: [48, 67]
      }
      
      // 绘制每个区域的连线
      for (const [region, [start, end]] of Object.entries(faceRegions)) {
        ctx.beginPath()
        for (let i = start; i <= end; i++) {
          const point = data.landmarks[i]
          if (i === start) {
            ctx.moveTo(point.x, point.y)
          } else {
            ctx.lineTo(point.x, point.y)
          }
        }
        if (region === 'rightEye' || region === 'leftEye' || region === 'mouth') {
          ctx.closePath()
        }
        ctx.strokeStyle = '#00FF00'
        ctx.stroke()
      }
      
      // 绘制关键点
      data.landmarks.forEach(point => {
        ctx.beginPath()
        ctx.arc(point.x, point.y, 1, 0, 2 * Math.PI)
        ctx.fill()
      })
    }
    
    // 绘制文字
    ctx.font = '16px Arial'
    ctx.fillStyle = ctx.strokeStyle
    let text = data.stu_id ? 
      `${data.cn_name} (${data.confidence.toFixed(1)}%)` : 
      (data.error || '无法识别')
    ctx.fillText(text, x, y - 5)
  }
}

const connectWebSocket = () => {
  // 如果已经有连接或正在连接中，直接返回
  if (ws.value?.readyState === WebSocket.OPEN || isConnecting.value) {
    return
  }
  
  isConnecting.value = true
  const wsUrl = `ws://${window.location.hostname}:8000/ws/face_recognition/`
  
  try {
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      console.log('WebSocket connected')
      isRecognizing.value = true
      isConnecting.value = false
    }
    
    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.error) {
        console.error(data.error)
      }
      drawRecognitionResult(data)
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
      ElMessage.error('WebSocket连接错误，请检查后端服务是否正常运行')
      isRecognizing.value = false
      isConnecting.value = false
      stopRecognition()  // 出错时停止识别
    }
    
    ws.value.onclose = (event) => {
      console.log('WebSocket closed with code:', event.code)
      ws.value = null
      isRecognizing.value = false
      isConnecting.value = false
      
      // 如果是非正常关闭，尝试重连
      if (event.code !== 1000 && event.code !== 1001) {
        setTimeout(() => {
          if (isRecognizing.value) {
            console.log('Attempting to reconnect...')
            connectWebSocket()
          }
        }, 3000)  // 3秒后重试
      }
    }
  } catch (error) {
    console.error('Failed to create WebSocket:', error)
    isConnecting.value = false
    ElMessage.error('无法创建WebSocket连接')
  }
}

const startRecognition = () => {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    connectWebSocket()
  }
  
  // 只有在没有定时器时才创建新的定时器
  if (!recognitionTimer) {
    recognitionTimer = setInterval(() => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        const context = canvas.value.getContext('2d')
        context.drawImage(video.value, 0, 0, 640, 480)
        const imageData = canvas.value.toDataURL('image/jpeg', 0.8)
        
        ws.value.send(JSON.stringify({
          image: imageData,
          equalize_hist: isEqualizeHistEnabled.value,
          detection_method: detectionMethod.value  // 添加检测方法参数
        }))
      }
    }, recognitionInterval.value)
  }
}

const stopRecognition = () => {
  isRecognizing.value = false
  
  if (recognitionTimer) {
    clearInterval(recognitionTimer)
    recognitionTimer = null
  }
  
  if (ws.value) {
    try {
      ws.value.close(1000)  // 正常关闭
    } catch (error) {
      console.error('Error closing WebSocket:', error)
    }
    ws.value = null
  }
  
  // 清除画布 - 添加判断
  if (overlayCanvas.value) {  // 确保 canvas 存在
    const ctx = overlayCanvas.value.getContext('2d')
    ctx.clearRect(0, 0, 640, 480)
  }
}

const addLog = (log) => {
  recognitionLogs.value.unshift(log)
  if (recognitionLogs.value.length > 100) {
    recognitionLogs.value.pop()
  }
}

const clearLogs = () => {
  recognitionLogs.value = []
}

const sendImageData = () => {
  if (ws.value?.readyState === WebSocket.OPEN) {
    const context = canvas.value.getContext('2d')
    context.drawImage(video.value, 0, 0, 640, 480)
    const imageData = canvas.value.toDataURL('image/jpeg', 0.8)
    
    ws.value.send(JSON.stringify({
      image: imageData,
      equalize_hist: isEqualizeHistEnabled.value,
      detection_method: detectionMethod.value  // 添加检测方法参数
    }))
  }
}

onMounted(() => {
  startCamera()
})

onUnmounted(() => {
  // 先停止摄像头
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
  }
  
  // 清理 WebSocket
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
  
  // 最后停止识别
  if (isRecognizing.value) {
    stopRecognition()
  }
})
</script>

<style scoped>
.camera-card, .settings-card, .log-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.camera-container {
  display: flex;
  justify-content: center;
}

.video-wrapper {
  position: relative;
  width: 640px;
  height: 480px;
}

.video-wrapper video,
.face-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 640px;
  height: 480px;
}

.face-overlay {
  z-index: 1;
  pointer-events: none;
}

.camera-container video {
  border: 2px solid #eee;
  border-radius: 4px;
}

.camera-container video.recognizing {
  border-color: #409EFF;
}

.log-container {
  height: 200px;
  overflow-y: auto;
}

.log-item {
  padding: 5px 0;
  border-bottom: 1px solid #eee;
}

.log-item .time {
  color: #999;
  margin-right: 10px;
}

.log-item .status {
  font-weight: bold;
}

.log-item .status.success {
  color: #67C23A;
}

.log-item .status.error {
  color: #F56C6C;
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

.el-radio-group {
  display: flex;
  gap: 20px;
}

.el-radio {
  margin-right: 0;
}
</style> 
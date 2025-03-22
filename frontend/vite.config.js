import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  server: {
    // 如果不再使用 HTTP 请求，可以删除代理配置
  }
}) 
import { createRouter, createWebHistory } from 'vue-router'
import DataRecord from '../views/DataRecord.vue'
import DataManage from '../views/DataManage.vue'
import FaceRecognition from '../views/FaceRecognition.vue'

const routes = [
  { 
    path: '/',
    redirect: '/record'
  },
  {
    path: '/record',
    name: 'DataRecord',
    component: DataRecord,
    meta: { keepAlive: false }  // 不缓存组件
  },
  {
    path: '/manage',
    name: 'DataManage', 
    component: DataManage,
    meta: { keepAlive: false }
  },
  {
    path: '/recognition',
    name: 'FaceRecognition',
    component: FaceRecognition,
    meta: { keepAlive: false }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 添加全局导航守卫
router.beforeEach((to, from, next) => {
  // 每次路由切换时强制重新创建组件
  to.meta.reload = true
  next()
})

export default router 
/**
 * 路由配置
 * 包含路由守卫：未登录用户自动跳转到登录页
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/home',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true, title: '主页' },
  },
  {
    path: '/create',
    name: 'CreatePerson',
    component: () => import('../views/CreatePerson.vue'),
    meta: { requiresAuth: true, title: '创建数字人' },
  },
  {
    path: '/chat/:personId',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
    meta: { requiresAuth: true, title: '对话' },
    props: true,
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: { requiresAuth: true, title: '我的档案' },
  },
  // 兜底：404 重定向至首页
  { path: '/:pathMatch(.*)*', redirect: '/home' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：验证登录状态
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  const isLoggedIn = !!token

  document.title = to.meta.title ? `${to.meta.title} · 数字伙伴` : '数字伙伴'

  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && isLoggedIn) {
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
/**
 * API 请求层
 * 统一封装 axios 实例，自动注入 JWT token，处理 401 跳转
 */
import axios from 'axios'
import { useUserStore } from '../stores/user'
import router from '../router'

// 创建 axios 实例（baseURL 为空，走 Vite 代理）
const api = axios.create({
  baseURL: '',
  timeout: 600000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动注入 Bearer token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：处理 401 自动跳转登录
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.clear()
      router.push('/login')
    }
    return Promise.reject(error.response?.data || error)
  }
)

// ── 认证接口 ─────────────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  getMe: () => api.get('/api/auth/me'),
}

// ── 数字人接口 ───────────────────────────────────────────────────────────────
export const digitalPersonAPI = {
  create: (data) => api.post('/api/digital-persons/', data),
  list: () => api.get('/api/digital-persons/'),
  get: (id) => api.get(`/api/digital-persons/${id}`),
  update: (id, data) => api.put(`/api/digital-persons/${id}`, data),
  delete: (id) => api.delete(`/api/digital-persons/${id}`),
  extractMedia: (formData) => api.post('/api/extract/media', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  uploadVideo: (id, formData) => api.post(`/api/digital-persons/${id}/video`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
}

// ── 对话接口 ─────────────────────────────────────────────────────────────────
export const conversationAPI = {
  sendMessage: (data) => api.post('/api/conversations/message', data),
  list: () => api.get('/api/conversations/'),
  get: (id) => api.get(`/api/conversations/${id}`),
  delete: (id) => api.delete(`/api/conversations/${id}`),
}

// ── 记忆接口（完整 CRUD）────────────────────────────────────────────────────
export const memoryAPI = {
  getByPerson: (digitalPersonId) => api.get(`/api/memories/${digitalPersonId}`),
  create: (data) => api.post('/api/memories/', data),
  update: (memoryId, data) => api.put(`/api/memories/${memoryId}`, data),
  delete: (memoryId) => api.delete(`/api/memories/${memoryId}`),
}



// ── 用户档案接口 ──────────────────────────────────────────────────────────────
export const profileAPI = {
  get: () => api.get('/api/profile/'),
  update: (data) => api.put('/api/profile/', data),
  uploadResume: (data) => api.post('/api/profile/resume', data),
}

// ── 数字人 Prompt 预览接口 ────────────────────────────────────────────────────
export const personaAPI = {
  previewPrompt: (personId) => api.get(`/api/digital-persons/${personId}/preview-prompt`),
}

export default api
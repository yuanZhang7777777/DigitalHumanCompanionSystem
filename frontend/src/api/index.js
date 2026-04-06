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
  sendMessageStream: async (data, onChunk) => {
    // 流式输出API（SSE）
    const token = localStorage.getItem('access_token')
    const headers = {
      'Content-Type': 'application/json',
    }
    
    // 添加认证Token（修复403错误）
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch('/api/conversations/message/stream', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.clear()
        window.location.href = '/login'
      }
      throw new Error(`请求失败: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // 保留未完成的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            
            // ✅ 兼容多种SSE格式（chunk/content/meta_start/done）
            if (parsed.chunk && onChunk) {
              // 后端流式输出格式：{"chunk": "文本"}
              onChunk(parsed.chunk)
            } else if (parsed.content && onChunk) {
              // 标准SSE格式：{"content": "文本"}
              onChunk(parsed.content)
            }
            // 忽略 meta_start 和 done 信号
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  },
  list: () => api.get('/api/conversations/'),
  get: (id) => api.get(`/api/conversations/${id}`),
  delete: (id) => api.delete(`/api/conversations/${id}`),
  deleteMessage: (conversationId, messageId) => api.delete(`/api/conversations/${conversationId}/messages/${messageId}`),
  uploadFile: (formData) => api.post('/api/conversations/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  analyzeJD: (data) => api.post('/api/conversations/analyze-jd', data),
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
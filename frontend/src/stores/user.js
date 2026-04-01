/**
 * 用户状态管理 Store
 * 管理 JWT token、用户信息、数字人列表
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI, digitalPersonAPI } from '../api'

export const useUserStore = defineStore('user', () => {
  // ── 状态 ──────────────────────────────────────────────────────────────────
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const userId = ref(localStorage.getItem('user_id') || '')
  const username = ref(localStorage.getItem('username') || '')
  const nickname = ref(localStorage.getItem('nickname') || '')
  const digitalPersons = ref([])
  const currentPerson = ref(null)

  // ── 计算属性 ──────────────────────────────────────────────────────────────
  const isLoggedIn = computed(() => !!accessToken.value && !!userId.value)
  // 供模板直接访问用户信息的统一入口
  const currentUser = computed(() => isLoggedIn.value ? {
    id: userId.value,
    username: username.value,
    nickname: nickname.value,
  } : null)

  // ── 认证操作 ──────────────────────────────────────────────────────────────

  /** 注册 */
  const register = async (uname, password, nick, email) => {
    try {
      const res = await authAPI.register({ username: uname, password, nickname: nick, email })
      if (res.success) {
        _saveAuth(res.data)
        return { success: true }
      }
      return { success: false, message: res.message }
    } catch (err) {
      return { success: false, message: err?.response?.data?.detail || err.message || '注册失败' }
    }
  }

  /** 登录 */
  const login = async (email, password) => {
    try {
      const res = await authAPI.login({ email, password })
      if (res.success) {
        _saveAuth(res.data)
        return { success: true }
      }
      return { success: false, message: res.message }
    } catch (err) {
      return { success: false, message: err?.response?.data?.detail || err.message || '登录失败' }
    }
  }

  /** 退出登录 */
  const logout = () => {
    accessToken.value = ''
    userId.value = ''
    username.value = ''
    nickname.value = ''
    digitalPersons.value = []
    currentPerson.value = null
    localStorage.clear()
  }

  /** 保存认证信息到本地存储 */
  const _saveAuth = (data) => {
    accessToken.value = data.access_token
    userId.value = data.user.id
    username.value = data.user.username
    nickname.value = data.user.nickname

    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user_id', data.user.id)
    localStorage.setItem('username', data.user.username)
    localStorage.setItem('nickname', data.user.nickname)
  }

  // ── 数字人操作 ────────────────────────────────────────────────────────────

  /** 加载数字人列表 */
  const loadDigitalPersons = async () => {
    if (!isLoggedIn.value) return
    try {
      const res = await digitalPersonAPI.list()
      if (res.success) {
        digitalPersons.value = res.data
      }
    } catch (err) {
      console.error('加载数字人列表失败:', err)
    }
  }

  /** 创建数字人 */
  const createDigitalPerson = async (personData) => {
    try {
      const res = await digitalPersonAPI.create(personData)
      if (res.success) {
        await loadDigitalPersons()
        return { success: true, data: res.data }
      }
      return { success: false, message: res.message }
    } catch (err) {
      return { success: false, message: err.message || '创建失败' }
    }
  }

  /** 删除数字人 */
  const deleteDigitalPerson = async (personId) => {
    try {
      const res = await digitalPersonAPI.delete(personId)
      if (res.success) {
        await loadDigitalPersons()
        if (currentPerson.value?.id === personId) {
          currentPerson.value = null
        }
        return { success: true }
      }
      return { success: false, message: res.message }
    } catch (err) {
      return { success: false, message: err.message || '删除失败' }
    }
  }

  /** 设置当前数字人 */
  const setCurrentPerson = (person) => {
    currentPerson.value = person
  }

  return {
    accessToken,
    userId,
    username,
    nickname,
    currentUser,
    digitalPersons,
    currentPerson,
    isLoggedIn,
    register,
    login,
    logout,
    loadDigitalPersons,
    createDigitalPerson,
    deleteDigitalPerson,
    setCurrentPerson,
  }
})
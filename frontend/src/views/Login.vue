<template>
  <div class="login-page">
    <div class="login-container animate-fade-up">
      <!-- 头部 Brand -->
      <div class="login-header">
        <h1 class="login-brand-name">数字伙伴</h1>
        <p class="login-brand-tagline">构建有温度的 AI 数字陪伴体验</p>
      </div>

      <!-- 表单卡片 -->
      <div class="login-card clean-pane">
        <!-- 切换标签 -->
        <div class="login-tabs">
          <button :class="['login-tab', { active: isLogin }]" @click="switchMode(true)">登录</button>
          <button :class="['login-tab', { active: !isLogin }]" @click="switchMode(false)">注册</button>
        </div>

        <!-- 错误提示 -->
        <div v-if="errorMsg" class="error-banner animate-scale-in">{{ errorMsg }}</div>

        <!-- 表单 -->
        <form class="login-form" @submit.prevent="handleSubmit" novalidate>
          <div v-if="!isLogin" class="form-group animate-fade-up">
            <label class="form-label">用户名</label>
            <input v-model="form.username" class="form-input" type="text" placeholder="用于登录的唯一标识" autocomplete="username" />
          </div>

          <div v-if="!isLogin" class="form-group animate-fade-up delay-1">
            <label class="form-label">昵称</label>
            <input v-model="form.nickname" class="form-input" type="text" placeholder="别人怎么称呼你" />
          </div>

          <div class="form-group animate-fade-up delay-1">
            <label class="form-label">邮箱</label>
            <input v-model="form.email" class="form-input" type="email" placeholder="your@email.com" autocomplete="email" />
          </div>

          <div class="form-group animate-fade-up delay-2">
            <label class="form-label">密码</label>
            <div class="input-with-icon">
              <input v-model="form.password" class="form-input" :type="showPassword ? 'text' : 'password'" placeholder="至少 6 位" autocomplete="current-password" />
              <button type="button" class="input-icon-btn" @click="showPassword = !showPassword">
                <svg v-if="!showPassword" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </button>
            </div>
          </div>

          <button type="submit" class="btn btn-primary btn-full submit-btn animate-fade-up delay-3" :class="{ 'btn-loading': loading }">
            <span v-if="loading" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:#fff"></span>
            <span v-else>{{ isLogin ? '登录' : '注册账号' }}</span>
          </button>
        </form>

        <p class="login-switch-hint">
          {{ isLogin ? '还没有账号？' : '已有账号？' }}
          <a @click="switchMode(!isLogin)">{{ isLogin ? '立即注册' : '返回登录' }}</a>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const isLogin = ref(true)
const showPassword = ref(false)
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({ username: '', nickname: '', email: '', password: '' })

const switchMode = (toLogin) => {
  isLogin.value = toLogin
  errorMsg.value = ''
  Object.assign(form, { username: '', nickname: '', email: '', password: '' })
}

watch(isLogin, () => { showPassword.value = false })

const handleSubmit = async () => {
  errorMsg.value = ''

  if (!form.email || !form.email.includes('@')) {
    errorMsg.value = '请填写正确的邮箱地址'; return
  }
  if (!form.password || form.password.length < 6) {
    errorMsg.value = '密码至少需要 6 位'; return
  }
  if (!isLogin.value) {
    if (!form.username?.trim()) { errorMsg.value = '请填写用户名'; return }
    if (!form.nickname?.trim()) { errorMsg.value = '请填写昵称'; return }
  }

  loading.value = true
  let res

  if (isLogin.value) {
    res = await userStore.login(form.email, form.password)
  } else {
    res = await userStore.register(form.username, form.password, form.nickname, form.email)
  }

  loading.value = false

  if (res.success) {
    const redirect = new URLSearchParams(window.location.search).get('redirect')
    router.push(redirect || '/home')
  } else {
    errorMsg.value = res.message || (isLogin.value ? '登录失败，请检查邮箱和密码' : '注册失败，请稍后重试')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  /* 依赖于 App.vue 全局的 ParticleBackground，故本身透明 */
  background: transparent; 
}

.login-container {
  width: 100%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-brand-name {
  font-size: clamp(2.25rem, 4vw, 3rem);
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--c-black);
  margin-bottom: 8px;
}

.login-brand-tagline {
  font-size: 1rem;
  color: var(--c-gray-600);
}

.login-card {
  width: 100%;
  padding: var(--space-8) var(--space-10);
  /* clean-pane 类已经从 style.css 中继承了圆角、模糊和轻阴影 */
}

/* 标签切换 */
.login-tabs {
  display: flex;
  border-bottom: 1px solid var(--c-gray-100);
  margin-bottom: var(--space-8);
}

.login-tab {
  padding: 12px 0;
  margin-right: var(--space-8);
  background: none;
  border: none;
  font-family: var(--font);
  font-size: 1rem;
  font-weight: 500;
  color: var(--c-gray-400);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all var(--dur-fast);
  letter-spacing: -0.01em;
}

.login-tab.active {
  color: var(--c-google-blue);
  border-bottom-color: var(--c-google-blue);
}

/* 错误提示 */
.error-banner {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  margin-bottom: var(--space-5);
  line-height: 1.5;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* 密码输入框 */
.input-with-icon {
  position: relative;
}

.input-with-icon .form-input {
  padding-right: 44px;
}

.input-icon-btn {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--c-gray-400);
  display: flex;
  padding: 4px;
  transition: color var(--dur-fast);
}
.input-icon-btn:hover { color: var(--c-black); }

/* 提交按钮 */
.submit-btn {
  margin-top: var(--space-2);
  height: 52px;
  font-size: 1.05rem;
}

/* 切换提示 */
.login-switch-hint {
  margin-top: var(--space-6);
  text-align: center;
  font-size: 0.9rem;
  color: var(--c-gray-500);
}

.login-switch-hint a {
  color: var(--c-google-blue);
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
}
.login-switch-hint a:hover {
  text-decoration: underline;
}

@media (max-width: 480px) {
  .login-card {
    padding: var(--space-6);
    border: none;
    box-shadow: none;
    background: transparent;
    backdrop-filter: none;
  }
}
</style>

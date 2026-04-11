<template>
  <div class="home-page">
    <!-- 顶部导航 -->
    <header class="app-header">
      <div class="container">
        <span class="app-logo">数字伙伴</span>
        <nav class="app-nav">
          <span class="nav-link" @click="$router.push('/profile')">我的档案</span>
          <button class="btn btn-ghost btn-sm" @click="handleLogout">退出</button>
        </nav>
      </div>
    </header>

    <main class="home-main">
      <div class="container">
        <!-- 欢迎区 -->
        <section class="welcome-section animate-fade-up">
          <div class="welcome-top">
            <div>
              <p class="welcome-greeting">你好，{{ userStore.nickname || userStore.username || '朋友' }}</p>
              <h1 class="welcome-title">你的数字伙伴</h1>
            </div>
            <button class="btn btn-primary" @click="$router.push('/create')">
              <span>+</span> 创建新伙伴
            </button>
          </div>
          <p class="welcome-sub delay-1 animate-fade-up">
            每一位数字伙伴都有独特的性格与经历，和他们聊聊你的困惑吧
          </p>
        </section>

        <hr class="divider" />

        <!-- 数字人列表 -->
        <section class="persons-section">
          <!-- 加载中 -->
          <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <span>加载中...</span>
          </div>

          <!-- 空状态 -->
          <div v-else-if="!persons.length" class="empty-state animate-fade-up">
            <div class="empty-state-icon">🤝</div>
            <h3>还没有数字伙伴</h3>
            <p>创建你的第一个数字伙伴，他会是一位有温度、有经历的朋友</p>
            <button class="btn btn-primary" @click="$router.push('/create')">立即创建</button>
          </div>

          <!-- 数字人网格 -->
          <div v-else class="persons-grid">
            <article
              v-for="(person, i) in persons"
              :key="person.id"
              class="person-card dynamic-card animate-fade-up"
              :class="`delay-${Math.min(i + 1, 5)}`"
              @click="goChat(person)"
            >
              <!-- 头部：头像 + 名字 -->
              <div class="person-card-header">
                <div class="person-avatar">
                  <img v-if="person.avatar" :src="person.avatar" :alt="person.name" />
                  <span v-else class="person-avatar-text">{{ person.name[0] }}</span>
                </div>
                <div class="person-info">
                  <h3 class="person-name">{{ person.name }}</h3>
                  <span class="person-relation tag">{{ person.relationship }}</span>
                </div>
                <!-- 操作菜单 -->
                <div class="person-actions" @click.stop>
                  <button class="btn btn-ghost btn-icon" title="编辑" @click="editPerson(person)">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button class="btn btn-ghost btn-icon" title="删除" @click="confirmDelete(person)">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- 性格标签 -->
              <div v-if="person.personality_traits?.length" class="person-tags">
                <span v-for="tag in person.personality_traits.slice(0, 4)" :key="tag" class="tag">{{ tag }}</span>
                <span v-if="person.personality_traits.length > 4" class="tag tag-count">
                  +{{ person.personality_traits.length - 4 }}
                </span>
              </div>

              <!-- 简介 -->
              <p v-if="person.background_story" class="person-story">
                {{ person.background_story.slice(0, 80) }}{{ person.background_story.length > 80 ? '…' : '' }}
              </p>

              <!-- 底部 -->
              <div class="person-card-footer">
                <span class="person-date">{{ formatDate(person.created_at) }}</span>
                <button class="btn btn-primary btn-sm" @click.stop="goChat(person)">开始聊天 →</button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="modal animate-scale-in">
        <h3>确认删除</h3>
        <p>确定要删除「{{ deleteTarget.name }}」吗？删除后将无法恢复，相关聊天记录也会一并删除。</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="deleteTarget = null">取消</button>
          <button class="btn btn-danger" :class="{ 'btn-loading': deleting }" @click="doDelete">
            {{ deleting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div class="toast" :class="{ show: toast.show }">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const persons = ref([])
const loading = ref(true)
const deleteTarget = ref(null)
const deleting = ref(false)
const toast = ref({ show: false, msg: '' })

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

// 加载数字人列表
const loadPersons = async () => {
  loading.value = true
  
  // 安全超时：10秒后如果还没加载完，强制停止加载状态并显示提示
  const timeoutId = setTimeout(() => {
    if (loading.value) {
      loading.value = false
      showToast('加载超时，请检查网络或刷新重试')
      console.warn('Digital persons loading timed out.')
    }
  }, 10000)

  try {
    await userStore.loadDigitalPersons()
    persons.value = userStore.digitalPersons
  } catch (err) {
    showToast('加载失败')
    console.error(err)
  } finally {
    clearTimeout(timeoutId)
    loading.value = false
  }
}

// 进入聊天
const goChat = (person) => {
  userStore.setCurrentPerson(person)
  router.push(`/chat/${person.id}`)
}

// 编辑（跳转到创建页面带 person 数据）
const editPerson = (person) => {
  router.push({ name: 'CreatePerson', query: { edit: person.id } })
}

// 触发删除确认
const confirmDelete = (person) => {
  deleteTarget.value = person
}

// 执行删除
const doDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  const res = await userStore.deleteDigitalPerson(deleteTarget.value.id)
  deleting.value = false
  deleteTarget.value = null
  if (res.success) {
    persons.value = userStore.digitalPersons
    showToast('已删除')
  } else {
    showToast('删除失败：' + (res.message || '未知错误'))
  }
}

// 退出登录
const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}

// Toast 提示
const showToast = (msg) => {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 2500)
}

onMounted(loadPersons)
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: transparent;
}

.home-main {
  padding: var(--space-12) 0 var(--space-16);
}

/* 欢迎区 */
.welcome-section {
  padding: var(--space-6) 0 var(--space-5);
}

.welcome-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-6);
  flex-wrap: wrap;
}

.welcome-greeting {
  font-size: 0.875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--c-primary);
  margin-bottom: var(--space-2);
}

.welcome-title {
  font-family: var(--font-serif);
  font-size: clamp(2rem, 3.5vw, 2.75rem);
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--c-anthropic-black);
}

.welcome-sub {
  margin-top: var(--space-2);
  font-size: 1rem;
  color: var(--c-olive-gray);
}

/* 加载状态 */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-16);
  color: var(--c-gray-400);
  font-size: 0.9rem;
}

/* 数字人网格 */
.persons-section {
  padding-top: var(--space-6);
}

.persons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-5);
}

/* 数字人卡片已复用 global .dynamic-card */
.person-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  cursor: pointer;
  background: var(--c-ivory);
  border: 1px solid var(--c-border-cream);
}

.person-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.person-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-200);
}

.person-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.person-avatar-text {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 500;
  color: var(--c-charcoal-warm);
}

.person-info {
  flex: 1;
  min-width: 0;
}

.person-name {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--c-anthropic-black);
  margin-bottom: 4px;
}

.person-relation {
  font-size: 0.75rem;
}

.person-actions {
  display: flex;
  gap: var(--space-1);
  margin-left: auto;
  opacity: 0;
  transition: opacity var(--dur-fast);
}

.person-card:hover .person-actions {
  opacity: 1;
}

/* 标签 */
.person-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.tag-count {
  background: var(--c-gray-100);
  color: var(--c-stone-gray);
}

/* 简介 */
.person-story {
  font-size: 0.875rem;
  color: var(--c-olive-gray);
  line-height: 1.60;
  flex: 1;
}

/* 卡片底部 */
.person-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-3);
  border-top: 1px solid var(--c-border-warm);
  margin-top: auto;
}

.person-date {
  font-size: 0.75rem;
  color: var(--c-stone-gray);
  font-variant-numeric: tabular-nums;
}

/* 删除确认弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 20, 19, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal {
  background: var(--c-ivory);
  border: 1px solid var(--c-border-cream);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  max-width: 420px;
  width: calc(100% - 48px);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-shadow: var(--shadow-whisper);
}

.modal h3 {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 500;
  color: var(--c-anthropic-black);
}

.modal p {
  font-size: 0.90rem;
  color: var(--c-olive-gray);
  line-height: 1.60;
}

.modal-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  margin-top: var(--space-2);
}

.btn-danger {
  background: transparent;
  color: var(--c-error-crimson);
  border: 1px solid #e8c4c4;
}
.btn-danger:hover { background: #fef2f2; }
</style>
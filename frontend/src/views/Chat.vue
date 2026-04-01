<template>
  <div class="chat-page">
    <!-- 背景粒子特效 (随朗读状态改变) -->
    <ParticleBackground :isSpeaking="playingMsgId !== null" />
    <!-- ── 记忆 & 提示词侧边栏 ── -->
    <aside :class="['side-panel', { open: sidePanel !== '' }]">
      <!-- 侧边栏头部 -->
      <div class="side-panel-header">
        <div class="side-panel-tabs">
          <button :class="['sp-tab', { active: sidePanel === 'memory' }]" @click="openPanel('memory')">
            🧠 记忆
            <span v-if="memories.length" class="sp-badge">{{ memories.length }}</span>
          </button>
          <button :class="['sp-tab', { active: sidePanel === 'prompt' }]" @click="openPanel('prompt')">
            ⚙️ System Prompt
          </button>
        </div>
        <button class="sp-close" @click="sidePanel = ''" title="关闭">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- ── 记忆面板 ── -->
      <div v-if="sidePanel === 'memory'" class="sp-body">
        <div class="sp-toolbar">
          <span class="sp-count">{{ memories.length }} 条记忆</span>
          <button class="btn btn-primary btn-sm" @click="openAddMemory">+ 添加</button>
        </div>

        <!-- 记忆列表 -->
        <div v-if="memories.length" class="memory-list">
          <div
            v-for="mem in memories"
            :key="mem.id"
            class="memory-item"
            :class="`cat-${mem.category}`"
          >
            <!-- 查看/编辑 切换 -->
            <div v-if="editingMemId !== mem.id" class="memory-view">
              <div class="memory-meta">
                <span class="memory-cat-badge">{{ CATEGORY_MAP[mem.category] || mem.category }}</span>
                <span class="memory-score">{{ (mem.importance_score * 100).toFixed(0) }}%</span>
              </div>
              <p class="memory-content">{{ mem.content }}</p>
              <div class="memory-actions">
                <button class="mem-action-btn" @click="startEditMemory(mem)" title="编辑">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  编辑
                </button>
                <button class="mem-action-btn mem-delete-btn" @click="deleteMemory(mem.id)" title="删除">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                  </svg>
                  删除
                </button>
              </div>
            </div>

            <!-- 编辑模式 -->
            <div v-else class="memory-edit">
              <textarea v-model="editMemForm.content" class="mem-edit-input" rows="3"></textarea>
              <div class="mem-edit-row">
                <select v-model="editMemForm.category" class="mem-select">
                  <option v-for="(label, key) in CATEGORY_MAP" :key="key" :value="key">{{ label }}</option>
                </select>
                <div class="mem-edit-actions">
                  <button class="btn btn-primary btn-sm" :disabled="memSaving" @click="saveEditMemory(mem.id)">
                    {{ memSaving ? '…' : '保存' }}
                  </button>
                  <button class="btn btn-secondary btn-sm" @click="editingMemId = null">取消</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="sp-empty">
          <p>还没有记忆</p>
          <p class="sp-hint">多聊几句，{{ person?.name }} 会自动记住重要信息</p>
        </div>
      </div>

      <!-- ── System Prompt 面板 ── -->
      <div v-if="sidePanel === 'prompt'" class="sp-body">
        <p class="sp-desc">
          System Prompt 是 AI 扮演 {{ person?.name }} 时的核心指令，记忆内容会附加在其后作为额外参考。
          你可以在这里编辑它来改变 AI 的行为。
        </p>
        <div v-if="promptLoading" class="sp-loading">
          <div class="spinner"></div>
        </div>
        <textarea
          v-else
          v-model="promptText"
          class="prompt-editor"
          rows="20"
          placeholder="加载中..."
        ></textarea>
        <div class="sp-toolbar" style="margin-top:12px">
          <button class="btn btn-secondary btn-sm" @click="resetPrompt">重置为默认</button>
          <button class="btn btn-primary btn-sm" :disabled="promptSaving" @click="savePrompt">
            {{ promptSaving ? '保存中…' : '保存 Prompt' }}
          </button>
        </div>
        <p v-if="promptMsg" class="prompt-save-msg" :class="promptMsgType">{{ promptMsg }}</p>
      </div>
    </aside>

    <!-- ── 主聊天区 ── -->
    <div class="chat-main" :class="{ 'is-speaking': playingMsgId !== null }">
      <!-- 顶部栏 -->
      <header class="chat-header">
        <button class="btn btn-ghost btn-icon" @click="$router.push('/home')" title="返回">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 5l-7 7 7 7"/>
          </svg>
        </button>

        <div class="chat-person-info">
          <div class="chat-avatar">
            <video 
              v-if="playingMsgId !== null && person?.speaking_video_url" 
              :src="person.speaking_video_url" 
              autoplay loop muted playsinline 
              class="avatar-video"
            ></video>
            <img v-else-if="person?.avatar" :src="person.avatar" :alt="person?.name" />
            <span v-else>{{ person?.name?.[0] || '?' }}</span>
          </div>
          <div>
            <h2 class="chat-person-name">{{ person?.name || '加载中…' }}</h2>
            <span class="chat-person-role">{{ person?.relationship }}</span>
          </div>
        </div>

        <div class="chat-header-actions">
          <div v-if="currentEmotion" class="emotion-pill">
            {{ EMOTION_ICONS[currentEmotion] || '💬' }} {{ currentEmotion }}
          </div>
          <button
            :class="['btn btn-ghost btn-sm', { active: sidePanel === 'memory' }]"
            @click="togglePanel('memory')"
            title="记忆面板"
          >
            🧠
            <span v-if="memories.length" class="mem-count-badge">{{ memories.length }}</span>
          </button>
          <button
            :class="['btn btn-ghost btn-sm', { active: sidePanel === 'prompt' }]"
            @click="togglePanel('prompt')"
            title="System Prompt"
          >
            ⚙️
          </button>
        </div>
      </header>

      <!-- 消息区 -->
      <div class="messages-area" ref="messagesArea">
        <!-- 欢迎消息 -->
        <div v-if="messages.length === 0 && !loading" class="welcome-msg animate-fade-up">
          <div class="welcome-avatar">
            <video 
              v-if="playingMsgId !== null && person?.speaking_video_url" 
              :src="person.speaking_video_url" 
              autoplay loop muted playsinline 
              class="avatar-video"
            ></video>
            <img v-else-if="person?.avatar" :src="person.avatar" :alt="person?.name" />
            <span v-else>{{ person?.name?.[0] || '?' }}</span>
          </div>
          <div class="welcome-bubble">
            <p>你好！我是{{ person?.name }}，你的{{ person?.relationship }}。</p>
            <p style="margin-top:4px;color:var(--c-gray-500);font-size:0.875rem">有什么想聊的，随时告诉我 ✨</p>
          </div>
        </div>

        <!-- 历史消息 -->
        <div
          v-for="(msg, idx) in messages"
          :key="msg.id || idx"
          :class="['msg-row', msg.role === 'user' ? 'msg-row-user' : 'msg-row-ai']"
          @mouseenter="hoveredIdx = idx"
          @mouseleave="hoveredIdx = -1"
        >
          <!-- AI 头像 -->
          <div v-if="msg.role === 'assistant'" class="msg-avatar">
            <video 
              v-if="(playingMsgId === msg.id || playingMsgId === idx) && person?.speaking_video_url" 
              :src="person.speaking_video_url" 
              autoplay loop muted playsinline 
              class="avatar-video"
            ></video>
            <img v-else-if="person?.avatar" :src="person.avatar" :alt="person?.name" />
            <span v-else>{{ person?.name?.[0] }}</span>
          </div>

          <div class="bubble-wrap">
            <div :class="['bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-ai']">
              <p class="bubble-text">{{ msg.content }}</p>
              <div class="bubble-footer">
                <span v-if="msg.emotion" class="bubble-emotion">{{ msg.emotion }}</span>
                <span class="bubble-time">{{ formatTime(msg.timestamp) }}</span>
                <button
                  v-if="msg.role === 'assistant'"
                  class="btn btn-ghost btn-icon tts-btn"
                  :class="{ playing: playingMsgId === msg.id || playingMsgId === idx }"
                  @click="playTTS(msg.content, msg.id || idx)"
                  :title="playingMsgId === (msg.id || idx) ? '停止朗读' : '朗读'"
                >
                  <span class="tts-icon">{{ playingMsgId === (msg.id || idx) ? '⏹️' : '🔊' }}</span>
                </button>
              </div>
            </div>
            <!-- 悬停操作（使用绝对定位防止跳动） -->
            <div class="msg-ops" :class="msg.role === 'user' ? 'msg-ops-left' : 'msg-ops-right'">
              <button class="msg-op-btn" @click="redoMsg(idx)" v-if="msg.role === 'user'" title="重新编辑">✏️</button>
              <button class="msg-op-btn" @click="deleteMsg(idx)" title="删除">🗑️</button>
            </div>
          </div>
        </div>

        <!-- 打字动画 -->
        <div v-if="typing" class="msg-row msg-row-ai animate-fade-in">
          <div class="msg-avatar">
            <video 
              v-if="playingMsgId !== null && person?.speaking_video_url" 
              :src="person.speaking_video_url" 
              autoplay loop muted playsinline 
              class="avatar-video"
            ></video>
            <img v-else-if="person?.avatar" :src="person.avatar" :alt="person?.name" />
            <span v-else>{{ person?.name?.[0] }}</span>
          </div>
          <div class="bubble bubble-ai typing-bubble">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area" :class="{ 'is-editing': editState.active }">
        <button
          v-if="editState.active"
          class="voice-btn cancel-edit-btn"
          @click="cancelEditMsg"
          title="撤销修改"
        >✕</button>
        <!-- 语音按钮 -->
        <button
          class="voice-btn"
          :class="{ listening: isListening }"
          @click="toggleVoice"
          :title="isListening ? '停止语音' : '语音输入'"
        >{{ isListening ? '🔴' : '🎙️' }}</button>

        <textarea
          v-model="inputText"
          class="msg-input"
          placeholder="说点什么… (Enter 发送，Shift+Enter 换行)"
          rows="1"
          @keydown.enter.exact.prevent="sendMessage"
          @input="autoResize"
          ref="inputRef"
          :disabled="typing"
        ></textarea>

        <button
          class="send-btn"
          @click="sendMessage"
          :disabled="!inputText.trim() || typing"
        >
          <svg v-if="!typing" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
          </svg>
          <div v-else class="spinner" style="width:16px;height:16px;border-top-color:#fff;border-width:2px"></div>
        </button>
      </div>
    </div>

    <!-- 沉浸式动态视频播放巨幕 (画中画) -->
    <transition name="fade-scale">
      <div 
        class="video-presentation-overlay" 
        v-if="playingMsgId !== null && person?.speaking_video_url"
      >
        <div class="video-presentation-container">
          <video 
            :src="person.speaking_video_url" 
            autoplay 
            loop 
            muted 
            playsinline 
            class="presentation-video"
          ></video>
          <!-- 底部光晕装饰 -->
          <div class="presentation-glow"></div>
        </div>
      </div>
    </transition>

    <!-- 添加记忆弹窗 -->
    <div v-if="showAddMemory" class="modal-overlay" @click.self="showAddMemory = false">
      <div class="modal animate-scale-in">
        <h3>添加记忆</h3>
        <p style="font-size:0.85rem;color:var(--c-gray-500);margin-bottom:16px">
          手动添加一条 {{ person?.name }} 应该记住的信息（AI 回复时会参考所有记忆）
        </p>
        <div class="form-group">
          <label class="form-label">记忆内容</label>
          <textarea v-model="addMemForm.content" class="form-textarea" rows="3" placeholder="例如：用户正在准备互联网大厂的算法面试"></textarea>
        </div>
        <div class="form-group" style="margin-top:12px">
          <label class="form-label">分类</label>
          <select v-model="addMemForm.category" class="form-input">
            <option v-for="(label, key) in CATEGORY_MAP" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div class="modal-actions" style="margin-top:20px">
          <button class="btn btn-secondary" @click="showAddMemory = false">取消</button>
          <button class="btn btn-primary" :disabled="memSaving || !addMemForm.content.trim()" @click="submitAddMemory">
            {{ memSaving ? '添加中…' : '确认添加' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div class="toast" :class="{ show: toast.show }">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useUserStore } from '../stores/user'
import { conversationAPI, digitalPersonAPI, memoryAPI, personaAPI } from '../api'
import ParticleBackground from '../components/ParticleBackground.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const personId = route.params.personId

// 状态
const person = ref(null)
const messages = ref([])
const memories = ref([])
const inputText = ref('')
const typing = ref(false)
const loading = ref(true)
const conversationId = ref(null)
const messagesArea = ref(null)
const inputRef = ref(null)
const hoveredIdx = ref(-1)
const currentEmotion = ref('')
const editState = ref({ active: false, removedMessages: [], insertIdx: -1 })

// 侧边栏：'memory' | 'prompt' | ''
const sidePanel = ref('')

// 记忆编辑/添加
const editingMemId = ref(null)
const editMemForm = reactive({ content: '', category: 'personal' })
const memSaving = ref(false)
const showAddMemory = ref(false)
const addMemForm = reactive({ content: '', category: 'personal' })

// System Prompt
const promptText = ref('')
const promptOriginal = ref('')
const promptLoading = ref(false)
const promptSaving = ref(false)
const promptMsg = ref('')
const promptMsgType = ref('success')

// 语音
const isListening = ref(false)
let recognition = null
const playingMsgId = ref(null) // 记录当前正在正在朗读的消息ID/Index

// Toast
const toast = ref({ show: false, msg: '' })

const CATEGORY_MAP = {
  career: '职业规划',
  emotion: '情感状态',
  personal: '个人信息',
  goal: '目标计划',
  event: '重要经历',
}

const EMOTION_ICONS = {
  '焦虑': '😰', '迷茫': '😕', '压力': '😤', '沮丧': '😔',
  '孤独': '🥺', '愤怒': '😠', '悲伤': '😢',
  '开心': '😊', '平静': '😌', '期待': '✨',
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────
const formatTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesArea.value) {
    messagesArea.value.scrollTop = messagesArea.value.scrollHeight
  }
}

const autoResize = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

const focusInput = () => nextTick(() => inputRef.value?.focus())

const showToast = (msg) => {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 2500)
}

// ── 侧边栏控制 ────────────────────────────────────────────────────────────────
const openPanel = async (tab) => {
  sidePanel.value = tab
  if (tab === 'prompt') await loadPrompt()
}

const togglePanel = async (tab) => {
  if (sidePanel.value === tab) {
    sidePanel.value = ''
  } else {
    await openPanel(tab)
  }
}

// ── 记忆操作 ──────────────────────────────────────────────────────────────────
const loadMemories = async () => {
  try {
    const res = await memoryAPI.getByPerson(personId)
    if (res.success) memories.value = res.data.memories || []
  } catch (e) { console.error('加载记忆失败:', e) }
}

const startEditMemory = (mem) => {
  editingMemId.value = mem.id
  editMemForm.content = mem.content
  editMemForm.category = mem.category
}

const saveEditMemory = async (memId) => {
  if (!editMemForm.content.trim()) return
  memSaving.value = true
  try {
    const res = await memoryAPI.update(memId, {
      content: editMemForm.content.trim(),
      category: editMemForm.category,
    })
    if (res.success) {
      await loadMemories()
      editingMemId.value = null
      showToast('记忆已更新')
    }
  } catch (e) { showToast('更新失败') } finally { memSaving.value = false }
}

const deleteMemory = async (memId) => {
  try {
    const res = await memoryAPI.delete(memId)
    if (res.success) {
      memories.value = memories.value.filter(m => m.id !== memId)
      showToast('记忆已删除')
    }
  } catch (e) { showToast('删除失败') }
}

const openAddMemory = () => {
  addMemForm.content = ''
  addMemForm.category = 'personal'
  showAddMemory.value = true
}

const submitAddMemory = async () => {
  if (!addMemForm.content.trim()) return
  memSaving.value = true
  try {
    const res = await memoryAPI.create({
      digital_person_id: personId,
      content: addMemForm.content.trim(),
      category: addMemForm.category,
      importance_score: 0.8,
    })
    if (res.success) {
      await loadMemories()
      showAddMemory.value = false
      showToast('记忆已添加')
    }
  } catch (e) { showToast('添加失败') } finally { memSaving.value = false }
}

// ── System Prompt 操作 ────────────────────────────────────────────────────────
const loadPrompt = async () => {
  if (promptText.value && !promptLoading.value) return  // 已有缓存
  promptLoading.value = true
  try {
    const res = await personaAPI.previewPrompt(personId)
    if (res.success) {
      promptText.value = res.data.prompt || ''
      promptOriginal.value = promptText.value
    }
  } catch (e) {
    promptText.value = '加载失败：' + (e?.message || '未知错误')
  } finally { promptLoading.value = false }
}

const savePrompt = async () => {
  promptSaving.value = true
  promptMsg.value = ''
  try {
    // 调用数字人更新接口，保存自定义 system_prompt 覆盖
    const res = await digitalPersonAPI.update(personId, { system_prompt_override: promptText.value })
    if (res?.success !== false) {
      promptMsg.value = '已保存'
      promptMsgType.value = 'success'
      promptOriginal.value = promptText.value
      // 让下次重新拉取
      setTimeout(() => { promptMsg.value = '' }, 2000)
    } else {
      promptMsg.value = '保存失败'
      promptMsgType.value = 'error'
    }
  } catch (e) {
    promptMsg.value = '保存失败：' + (e?.message || '未知错误')
    promptMsgType.value = 'error'
  } finally { promptSaving.value = false }
}

const resetPrompt = () => {
  promptText.value = promptOriginal.value
  promptMsg.value = ''
}

// ── 消息操作 ──────────────────────────────────────────────────────────────────
const cancelEditMsg = () => {
  if (!editState.value.active) return
  messages.value.splice(editState.value.insertIdx, 0, ...editState.value.removedMessages)
  editState.value.active = false
  inputText.value = ''
  autoResize()
  scrollToBottom()
}

const deleteMsg = (idx) => {
  const msg = messages.value[idx]
  if (!msg) return
  if (msg.role === 'user') {
    const next = messages.value[idx + 1]
    messages.value.splice(idx, next?.role === 'assistant' ? 2 : 1)
  } else {
    messages.value.splice(idx, 1)
  }
  hoveredIdx.value = -1
}

const redoMsg = (idx) => {
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'user') return
  
  const next = messages.value[idx + 1]
  const count = next?.role === 'assistant' ? 2 : 1
  
  editState.value = {
    active: true,
    removedMessages: messages.value.slice(idx, idx + count),
    insertIdx: idx
  }
  
  inputText.value = msg.content
  autoResize()
  messages.value.splice(idx, count)
  hoveredIdx.value = -1
  focusInput()
}

// ── 发送消息 ──────────────────────────────────────────────────────────────────
const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || typing.value) return

  messages.value.push({ role: 'user', content: text, timestamp: new Date().toISOString() })
  inputText.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  typing.value = true
  await scrollToBottom()

  try {
    const res = await conversationAPI.sendMessage({
      digital_person_id: personId,
      message: text,
      conversation_id: conversationId.value,
    })

    if (res.success) {
      conversationId.value = res.data.conversation_id
      currentEmotion.value = res.data.emotion || ''
      messages.value.push({
        role: 'assistant',
        content: res.data.reply,
        emotion: res.data.emotion,
        timestamp: res.data.timestamp,
      })

      // ✅ 每轮对话结束后自动刷新记忆列表
      await loadMemories()
      editState.value.active = false // 发送成功，确认放弃被替换的消息
    }
  } catch (err) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我暂时无法回应，请稍后重试。',
      timestamp: new Date().toISOString(),
    })
  } finally {
    typing.value = false
    await scrollToBottom()
    focusInput()
  }
}

// ── 语音输入 ──────────────────────────────────────────────────────────────────
const initSpeech = () => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) return null
  const r = new SR()
  r.lang = 'zh-CN'
  r.continuous = false
  r.interimResults = true
  r.onresult = (e) => {
    inputText.value = Array.from(e.results).map(r => r[0].transcript).join('')
    autoResize()
  }
  r.onend = () => { isListening.value = false }
  r.onerror = () => { isListening.value = false }
  return r
}

const toggleVoice = () => {
  if (!recognition) recognition = initSpeech()
  if (!recognition) { alert('浏览器不支持语音输入，请使用 Chrome'); return }
  if (isListening.value) { recognition.stop(); isListening.value = false }
  else { recognition.start(); isListening.value = true }
}

// ── 语音朗读 (TTS) ────────────────────────────────────────────────────────────
const playTTS = (text, msgId) => {
  if (!text) return

  // 如果点击的是当前正在播放的消息，则停止
  if (playingMsgId.value === msgId) {
    if (window.currentAudio) {
      window.currentAudio.pause()
      window.currentAudio.src = '' // 阻断尚未完成的加载并释放资源
      window.currentAudio = null
    }
    playingMsgId.value = null
    return
  }

  // 停止之前正在播放的其他音频
  if (window.currentAudio) {
    window.currentAudio.pause()
    window.currentAudio.src = '' 
    window.currentAudio = null
  }

  playingMsgId.value = msgId

  // ✅ 生产环境修复：使用相对路径，让请求通过 Nginx 代理反向转发给后端
  // 不再使用 import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const url = `/api/tts/generate?text=${encodeURIComponent(text)}&lang=zh&person_id=${personId}`

  const audio = new Audio(url)
  window.currentAudio = audio
  
  audio.onended = () => {
    if (playingMsgId.value === msgId) {
      playingMsgId.value = null
    }
  }
  
  audio.onerror = () => {
    if (playingMsgId.value === msgId) {
      playingMsgId.value = null
    }
    // 只有在非中止错误时才提示
    if (audio.error && audio.error.code !== 4) {
      showToast('获取语音失败，请检查后端服务')
    }
  }
  
  audio.play().catch(e => {
    if (e.name !== 'AbortError') {
      showToast('播放语音失败。请检查后端及网络连接。')
      console.error('TTS Play Error:', e)
    }
    playingMsgId.value = null
  })
}

// ── 生命周期清除 ──────────────────────────────────────────────────────────────
onUnmounted(() => {
  // 切换路由离开组件时，安全停止后台仍在播放的音频
  if (window.currentAudio) {
    window.currentAudio.pause()
    window.currentAudio.src = ''
    window.currentAudio = null
  }
})

// ── 初始化 ────────────────────────────────────────────────────────────────────
onMounted(async () => {
  // 加载数字人
  try {
    if (userStore.currentPerson?.id === personId) {
      person.value = userStore.currentPerson
    } else {
      const res = await digitalPersonAPI.get(personId)
      if (res.success) person.value = res.data
    }
  } catch (e) { router.push('/home'); return }

  // 加载历史对话
  try {
    const listRes = await conversationAPI.list()
    if (listRes.success && listRes.data.length > 0) {
      const conv = listRes.data.find(c => c.digital_person_id === personId)
      if (conv) {
        conversationId.value = conv.id
        const cvRes = await conversationAPI.get(conv.id)
        if (cvRes.success && cvRes.data.messages) {
          messages.value = cvRes.data.messages
          await scrollToBottom()
        }
      }
    }
  } catch (e) { console.error('加载历史:', e) }

  // 加载记忆
  await loadMemories()

  loading.value = false
  focusInput()
})
</script>

<style scoped>
/* ── 布局 ─────────────────────────────────────────────────── */
.chat-page {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: transparent;
  position: relative;
}

/* 面板/层级调整以露出背景 */
.side-panel {
  z-index: 200;
  background: var(--c-white);
  width: 340px;
  border-right: 1px solid var(--c-gray-300);
  display: flex;
  flex-direction: column;
  transform: translateX(-100%);
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  transition: transform var(--dur-normal) var(--ease);
  box-shadow: none;
}

.side-panel.open {
  transform: translateX(0);
  box-shadow: 4px 0 32px rgba(0,0,0,0.08);
}

.side-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: var(--border);
  gap: 8px;
}

.side-panel-tabs {
  display: flex;
  gap: 4px;
}

.sp-tab {
  padding: 6px 16px;
  border-radius: var(--radius-full);
  font-size: 0.85rem;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--c-gray-600);
  cursor: pointer;
  transition: all var(--dur-fast);
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.sp-tab.active { 
  background: var(--c-google-blue-light); 
  color: var(--c-google-blue); 
}
.sp-tab:hover:not(.active) {
  background: var(--c-gray-100);
}

.sp-badge {
  background: var(--c-black);
  color: #fff;
  border-radius: 99px;
  font-size: 0.65rem;
  padding: 1px 6px;
  font-weight: 700;
}

.sp-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--c-gray-400);
  display: flex;
  padding: 6px;
  border-radius: var(--radius-md);
  transition: all var(--dur-fast);
}
.sp-close:hover { background: var(--c-gray-100); color: var(--c-black); }

/* 侧边栏内容区 */
.sp-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sp-count {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-gray-400);
}

.sp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  gap: 8px;
}
.sp-empty p { font-size: 0.9rem; color: var(--c-gray-600); }
.sp-hint { font-size: 0.8rem !important; color: var(--c-gray-400) !important; }

.sp-loading {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.sp-desc {
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--c-gray-500);
  padding: 10px;
  background: var(--c-gray-50);
  border-radius: var(--radius-md);
  border: var(--border);
}

/* ── 记忆列表 ─────────────────────────────────────────────── */
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-item {
  border: var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--c-white);
  transition: box-shadow var(--dur-fast);
}
.memory-item:hover { box-shadow: var(--shadow-sm); }

.memory-view { display: flex; flex-direction: column; gap: 8px; }

.memory-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.memory-cat-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--c-gray-100);
  color: var(--c-gray-700);
}

.memory-score {
  font-size: 0.7rem;
  color: var(--c-gray-400);
  font-variant-numeric: tabular-nums;
}

.memory-content {
  font-size: 0.85rem;
  color: var(--c-gray-700);
  line-height: 1.5;
}

.memory-actions {
  display: flex;
  gap: 8px;
}

.mem-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: var(--c-gray-400);
  border: none;
  background: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: all var(--dur-fast);
}
.mem-action-btn:hover { color: var(--c-black); background: var(--c-gray-100); }
.mem-delete-btn:hover { color: #dc2626 !important; }

/* 记忆编辑 */
.memory-edit { display: flex; flex-direction: column; gap: 8px; }
.mem-edit-input {
  width: 100%;
  border: var(--border);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  font-family: var(--font);
  font-size: 0.85rem;
  resize: vertical;
  outline: none;
}
.mem-edit-input:focus { border-color: var(--c-black); }

.mem-edit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mem-select {
  border: var(--border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  font-size: 0.8rem;
  font-family: var(--font);
  background: var(--c-white);
  outline: none;
  cursor: pointer;
}

.mem-edit-actions { display: flex; gap: 6px; }

/* System Prompt 编辑器 */
.prompt-editor {
  width: 100%;
  border: var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--c-gray-800);
  resize: vertical;
  outline: none;
  transition: border-color var(--dur-fast);
  background: var(--c-gray-50);
}
.prompt-editor:focus { border-color: var(--c-black); background: var(--c-white); }

.prompt-save-msg {
  font-size: 0.8rem;
  padding: 6px 10px;
  border-radius: var(--radius-md);
}
.prompt-save-msg.success { color: #15803d; background: #f0fdf4; }
.prompt-save-msg.error { color: #dc2626; background: #fef2f2; }

/* ── 主聊天区 ─────────────────────────────────────────────── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  z-index: 10; /* 置于背景之上 */
}

/* 顶部栏 */
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  height: 60px;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.chat-person-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.chat-avatar {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  border: var(--border);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-100);
  position: relative;
  flex-shrink: 0;
  font-weight: 700;
  font-size: 1rem;
}

.chat-avatar img { width: 100%; height: 100%; object-fit: cover; }

.online-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
  border: 2px solid #fff;
  position: absolute;
  bottom: 1px;
  right: 1px;
}

.chat-person-name {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--c-black);
}

.chat-person-role {
  font-size: 0.75rem;
  color: var(--c-gray-400);
  display: block;
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn.active {
  background: var(--c-gray-100);
  color: var(--c-black);
}

.emotion-pill {
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  background: var(--c-gray-100);
  color: var(--c-gray-700);
  border: var(--border);
}

.mem-count-badge {
  margin-left: 4px;
  background: var(--c-black);
  color: #fff;
  border-radius: 99px;
  font-size: 0.65rem;
  padding: 1px 6px;
  font-weight: 700;
}

/* ── 消息区 ───────────────────────────────────────────────── */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 32px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 欢迎消息 */
.welcome-msg {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 600px;
}

.welcome-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: var(--border);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-100);
  font-weight: 700;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.welcome-avatar img { width: 100%; height: 100%; object-fit: cover; }

.welcome-bubble {
  background: var(--c-white);
  border: 1px solid var(--c-gray-100);
  box-shadow: var(--shadow-sm);
  border-radius: 0 16px 16px 16px;
  padding: 14px 18px;
  font-size: 0.95rem;
  color: var(--c-black);
  line-height: 1.6;
}

/* 消息行 */
.msg-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.msg-row-user { flex-direction: row-reverse; }

.msg-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: var(--border);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-100);
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}
.msg-avatar img { width: 100%; height: 100%; object-fit: cover; }

.avatar-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: inherit;
  display: block;
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: min(600px, 72%);
  position: relative;
}

.msg-row-user .bubble-wrap { align-items: flex-end; }

.bubble {
  padding: 12px 18px;
  border-radius: var(--radius-xl);
  font-size: 0.95rem;
  line-height: 1.65;
  position: relative;
}

.bubble-ai {
  background: var(--c-white);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--c-gray-100);
  border-bottom-left-radius: 4px;
  color: var(--c-black);
}

.bubble-user {
  background: var(--c-google-blue);
  color: var(--c-white);
  border-bottom-right-radius: 4px;
  box-shadow: var(--shadow-sm);
}

.bubble-user .bubble-text {
  color: var(--c-white); 
}

.bubble-text { white-space: pre-wrap; word-break: break-word; }

.bubble-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.bubble-emotion {
  font-size: 0.7rem;
  color: var(--c-gray-400);
}

.bubble-time {
  font-size: 0.7rem;
  color: var(--c-gray-400);
  font-variant-numeric: tabular-nums;
}

.bubble-user .bubble-time { color: rgba(255,255,255,0.5); }

/* 悬停操作 (不再占据高度，防止跳动) */
.msg-ops {
  display: flex;
  gap: 4px;
  position: absolute;
  top: 10px;
  opacity: 0;
  pointer-events: none; /* 隐藏时不可点击 */
  transition: all 0.2s ease-in-out;
  transform: translateY(5px);
  z-index: 10;
}

/* 用户消息：气泡在右侧，操作按钮弹出在左边 */
.msg-row-user .msg-ops {
  right: 100%;
  left: auto;
  padding-right: 15px; /* 利用 padding 建立极度稳定的无界桥梁 */
}

/* AI消息：气泡在左侧，操作按钮弹出在右边 */
.msg-row-ai .msg-ops {
  left: 100%;
  right: auto;
  padding-left: 15px; /* 建立稳定的右手无界桥梁 */
}

.bubble-wrap:hover .msg-ops,
.msg-ops:hover {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.msg-op-btn {
  background: var(--c-white);
  border: var(--border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all var(--dur-fast);
}
.msg-op-btn:hover { background: var(--c-gray-100); }

/* 朗读播放状态动画与按钮灵敏度提升 */
.tts-btn { 
  transition: all 0.2s; 
  cursor: pointer;
  padding: 6px;
  margin: -6px; /* 增大热区但不影响排版 */
  border-radius: 50%;
}
.tts-btn:hover {
  background: rgba(0,0,0,0.04);
  transform: scale(1.1);
}
.tts-btn.playing .tts-icon { color: #5b7cff; animation: pulseTTS 1.5s infinite; }
@keyframes pulseTTS {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.1); }
  100% { opacity: 1; transform: scale(1); }
}

/* 网页全局边框发光动效 */
.chat-main.is-speaking {
  /* 使用内阴影来实现全区域边缘发光 */
  animation: fullScreenPulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  box-shadow: inset 0 0 30px rgba(26, 115, 232, 0.4);
  transition: box-shadow 0.3s ease;
  border: 2px solid rgba(26, 115, 232, 0.5); /* 增加实体边框加亮 */
}

@keyframes fullScreenPulse {
  0% {
    box-shadow: inset 0 0 10px rgba(26, 115, 232, 0.2);
    border-color: rgba(26, 115, 232, 0.3);
  }
  50% {
    box-shadow: inset 0 0 50px rgba(26, 115, 232, 0.8), inset 0 0 10px rgba(26, 115, 232, 0.5);
    border-color: rgba(26, 115, 232, 0.9);
  }
  100% {
    box-shadow: inset 0 0 10px rgba(26, 115, 232, 0.2);
    border-color: rgba(26, 115, 232, 0.3);
  }
}

/* 打字动画 */
.typing-bubble {
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: var(--c-gray-400);
  border-radius: 50%;
  animation: typingBounce 1.2s ease-in-out infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* ── 输入区 (Floating Pill) ───────────────────────────────────────────────── */
.input-area {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 16px;
  margin: 0 40px 32px 40px; /* 让它浮空 */
  border-radius: var(--radius-full); /* 胶囊形状 */
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(24px);
  box-shadow: var(--shadow-lg); /* 高定悬浮弥散阴影 */
  z-index: 20;
}

.voice-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: var(--border);
  background: var(--c-white);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  transition: all var(--dur-fast);
}
.voice-btn:hover { background: var(--c-gray-100); }
.voice-btn.listening { background: #fee2e2; border-color: #fca5a5; }

.cancel-edit-btn {
  color: #dc2626;
  font-weight: 700;
  font-size: 0.9rem;
}
.cancel-edit-btn:hover { background: #fee2e2; border-color: #fca5a5; }

.msg-input {
  flex: 1;
  border: none;
  border-radius: var(--radius-full);
  padding: 12px 16px;
  font-family: var(--font);
  font-size: 0.95rem;
  resize: none;
  max-height: 140px;
  outline: none;
  line-height: 1.5;
  background: transparent;
  color: var(--c-black);
}
.msg-input:focus {
  background: transparent;
  box-shadow: none;
}
.msg-input::placeholder { color: var(--c-gray-400); }

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--c-black);
  color: var(--c-white);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--dur-fast) var(--ease);
}
.send-btn:hover { background: var(--c-gray-800); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; transform: none; cursor: not-allowed; }

/* ── 弹窗 ─────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal {
  background: var(--c-white);
  border: 1px solid var(--c-gray-100);
  border-radius: var(--radius-xl);
  padding: 32px;
  max-width: 440px;
  width: calc(100% - 48px);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
}

.modal h3 {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--c-black);
  margin-bottom: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* ── 沉浸式动态视频大屏 (画中画) ─────────────────────────────────────────────── */
.video-presentation-overlay {
  position: absolute;
  top: 80px; /* 避开头部栏 */
  right: 30px;
  width: 280px;
  height: 380px;
  z-index: 100;
  pointer-events: none; /* 让鼠标穿透，允许边看边滚动背景 */
}

.video-presentation-container {
  width: 100%;
  height: 100%;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.15),
              0 0 0 1px rgba(255,255,255,0.4) inset;
  background: var(--c-white);
  position: relative;
  /* 玻璃反射感 */
  backdrop-filter: blur(20px);
}

.presentation-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 营造全息投影底部发光感 */
.presentation-glow {
  position: absolute;
  bottom: -20px;
  left: 10%;
  right: 10%;
  height: 40px;
  background: var(--c-google-blue);
  filter: blur(30px);
  opacity: 0.6;
  z-index: -1;
  animation: presentationPulse 2s infinite alternate;
}

@keyframes presentationPulse {
  0% { opacity: 0.4; transform: scale(0.95); }
  100% { opacity: 0.8; transform: scale(1.05); }
}

/* 巨幕出入场动画 */
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

@media (max-width: 768px) {
  .video-presentation-overlay {
    top: auto;
    bottom: 100px;
    right: 50%;
    transform: translateX(50%);
    width: 200px;
    height: 280px;
  }
}
</style>

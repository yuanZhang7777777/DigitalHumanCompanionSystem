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
              <div v-if="msg.file_urls && msg.file_urls.length" class="msg-attachments">
                <div 
                  v-for="(url, i) in msg.file_urls" 
                  :key="i" 
                  class="msg-attachment-item"
                  @click.stop="previewAttachment(url)"
                >
                  <img 
                    v-if="url.match(/\.(jpeg|jpg|gif|png|webp|bmp)$/i)" 
                    :src="getFullUrl(url)" 
                    class="msg-img" 
                    @error="(e) => { e.target.src = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22><rect fill=%22%23f0f0f0%22 width=%22200%22 height=%22150%22 rx=%228%22/><text x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22>图片加载失败</text></svg>' }"
                  />
                  <video v-else :src="getFullUrl(url)" controls class="msg-video"></video>
                  <div class="msg-attachment-zoom">🔍</div>
                </div>
              </div>
              <p class="bubble-text" v-html="renderMarkdown(msg.content)" @mouseup="showSelectionMenu"></p>
              <div class="bubble-footer">
                <!-- 情绪分析按钮（仅用户消息显示） -->
                <button 
                  v-if="msg.role === 'user' && msg.emotion"
                  class="emotion-btn"
                  :class="`emotion-${msg.emotion_polarity || 'neutral'}`"
                  @click.stop="showEmotionAnalysis(msg)"
                  :title="`查看${msg.emotion}情绪分析`"
                >
                  {{ getEmotionIcon(msg.emotion) }}
                  <span>{{ msg.emotion }}</span>
                </button>
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
        <button
          class="voice-btn"
          :class="{ listening: isListening }"
          @click="toggleVoice"
          :title="isListening ? '停止语音' : '语音输入'"
        >{{ isListening ? '🔴' : '🎙️' }}</button>

        <!-- 附件上传按钮 -->
        <button
          class="voice-btn attachment-btn"
          @click="$refs.fileInput.click()"
          title="上传图片或视频"
        >📎</button>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/mov,video/avi"
          style="display:none"
          @change="handleFileUpload"
        />

        <!-- 附件预览区域 -->
        <div v-if="attachments.length" class="attachments-preview">
          <div 
            v-for="(att, idx) in attachments" 
            :key="idx" 
            class="attachment-item"
            @click="previewAttachment(att)"
          >
            <img v-if="att.type === 'image'" :src="getFullUrl(att.url)" class="attachment-thumb" @error="(e) => { e.target.src = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2240%22 height=%2240%22><rect fill=%22%23f0f0f0%22 width=%2240%22 height=%2240%22 rx=%228%22/><text x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22 font-size=%2212%22 fill=%22%23999%22>加载失败</text></svg>' }" />
            <div v-else class="attachment-thumb video-thumb">🎬</div>
            <div class="attachment-type-badge">{{ att.type === 'image' ? '🖼️' : '🎬' }}</div>
            <button class="attachment-remove" @click.stop="removeAttachment(idx)">✕</button>
          </div>
        </div>

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
          :disabled="(!inputText.trim() && attachments.length === 0) || typing"
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

    <!-- 选中文字操作菜单（类似豆包） -->
    <Teleport to="body">
      <div
        v-if="selectionMenu.show"
        class="selection-menu"
        :style="{ left: selectionMenu.x + 'px', top: selectionMenu.y + 'px' }"
      >
        <button class="selection-menu-item" @click="copySelectedText" title="复制">
          📋 复制
        </button>
        <button class="selection-menu-item" @click="speakSelectedText" title="朗读">
          🔊 朗读
        </button>
        <button class="selection-menu-item" @click="explainSelectedText" title="让AI解释">
          💬 解释
        </button>
        <button class="selection-menu-item" @click="addToConversation" title="继续讨论">
          ➕ 继续讨论
        </button>
      </div>
    </Teleport>

    <!-- 情绪分析弹窗 -->
    <Teleport to="body">
      <div v-if="emotionAnalysis.show" class="modal-overlay emotion-modal-overlay" @click.self="emotionAnalysis.show = false">
        <div class="modal emotion-analysis-modal animate-scale-in">
          <h3>🧠 情绪分析</h3>
          
          <div class="emotion-display" :class="`emotion-display-${emotionAnalysis.polarity}`">
            <span class="emotion-big-icon">{{ getEmotionIcon(emotionAnalysis.emotion) }}</span>
            <div class="emotion-info">
              <span class="emotion-name">{{ emotionAnalysis.emotion }}</span>
              <span class="emotion-level">{{ getEmotionLevel(emotionAnalysis.polarity) }}</span>
            </div>
          </div>

          <div class="emotion-suggestions" v-if="emotionAnalysis.suggestions.length">
            <h4>💡 情绪建议</h4>
            <ul>
              <li v-for="(suggestion, i) in emotionAnalysis.suggestions" :key="i">{{ suggestion }}</li>
            </ul>
          </div>

          <div class="emotion-actions">
            <button class="btn btn-primary" @click="askAboutEmotion">
              🤔 让AI分析这个情绪
            </button>
            <button class="btn btn-secondary" @click="emotionAnalysis.show = false">
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 情绪分析弹窗 -->
    
    <!-- Lightbox 图片/视频放大预览 -->
    <Teleport to="body">
      <div v-if="lightbox.show" class="lightbox-overlay" @click.self="closeLightbox" @keydown.esc="closeLightbox" tabindex="-1">
        <div class="lightbox-container">
          <!-- 关闭按钮 -->
          <button class="lightbox-close" @click="closeLightbox">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          
          <!-- 加载状态 -->
          <div v-if="lightbox.loading" class="lightbox-loading">
            <div class="spinner-large"></div>
            <p>加载中...</p>
          </div>
          
          <!-- 内容区域 -->
          <div v-else class="lightbox-content">
            <!-- 图片 -->
            <img 
              v-if="lightbox.type === 'image'" 
              :src="lightbox.url" 
              class="lightbox-image"
              alt="预览图片"
              @wheel.prevent="handleZoom"
            />
            
            <!-- 视频 -->
            <video 
              v-else-if="lightbox.type === 'video'" 
              :src="lightbox.url"
              class="lightbox-video"
              controls
              autoplay
              muted
            ></video>
          </div>
          
          <!-- 底部工具栏 -->
          <div class="lightbox-toolbar">
            <button v-if="lightbox.type === 'image'" @click="downloadMedia(lightbox.url)" class="toolbar-btn">
              📥 下载
            </button>
            <span class="toolbar-info">{{ lightbox.type === 'image' ? '🖼️ 图片预览' : '🎬 视频预览' }}</span>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import gsap from 'gsap'
import { marked } from 'marked'
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

// 情绪分析弹窗状态
const emotionAnalysis = reactive({
  show: false,
  emotion: '',
  polarity: 'neutral',
  messageContent: '',
  suggestions: []
})

// 情绪图标映射
const EMOTION_ICON_MAP = {
  '焦虑': '😰', '迷茫': '😕', '压力': '😤', '沮丧': '😔',
  '孤独': '🥺', '愤怒': '😠', '悲伤': '😢', '恐惧': '😨',
  '兴奋': '🤩', '开心': '😊', '满足': '😌', '平静': '😐',
  '期待': '🤗', '惊讶': '😲', '困惑': '🤔', '疲惫': '😫'
}

// 获取情绪图标
const getEmotionIcon = (emotion) => {
  return EMOTION_ICON_MAP[emotion] || '😐'
}

// 获取情绪级别描述
const getEmotionLevel = (polarity) => {
  const levels = {
    'positive': '积极情绪',
    'negative': '消极情绪',
    'neutral': '中性情绪'
  }
  return levels[polarity] || '未知'
}

// 显示情绪分析
const showEmotionAnalysis = (msg) => {
  emotionAnalysis.show = true
  emotionAnalysis.emotion = msg.emotion || '平静'
  emotionAnalysis.polarity = msg.emotion_polarity || 'neutral'
  emotionAnalysis.messageContent = msg.content || ''
  
  // 根据情绪生成建议
  emotionAnalysis.suggestions = generateEmotionSuggestions(msg.emotion, msg.emotion_polarity)
}

// 根据情绪生成建议
const generateEmotionSuggestions = (emotion, polarity) => {
  const suggestionMap = {
    '焦虑': ['深呼吸放松', '尝试分解问题', '找人倾诉', '适当运动缓解'],
    '迷茫': ['列出目标清单', '寻求他人建议', '回顾过往经验', '给自己时间思考'],
    '压力': ['优先处理重要事项', '学会说"不"', '保证充足睡眠', '尝试冥想'],
    '沮丧': ['记录感恩日记', '做喜欢的事', '联系朋友', '寻求专业帮助'],
    '孤独': ['主动联系朋友', '参加社交活动', '培养兴趣爱好', '考虑志愿服务'],
    '愤怒': ['暂时离开现场', '深呼吸冷静', '写下感受', '运动发泄'],
    '兴奋': ['分享喜悦', '记录此刻', '保持积极', '设定新目标'],
    '开心': ['享受当下', '分享快乐', '保持健康习惯', '帮助他人']
  }
  
  return suggestionMap[emotion] || ['保持积极心态', '关注当下', '照顾好自己']
}

// 让AI分析当前情绪
const askAboutEmotion = () => {
  if (!emotionAnalysis.messageContent) return
  
  inputText.value = `我刚表达了"${emotionAnalysis.emotion}"的情绪，能帮我分析一下这个情绪的原因吗？并给出一些建议。`
  emotionAnalysis.show = false
  focusInput()
  sendMessage()
}

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

// 获取完整的资源URL（处理相对路径）
const getFullUrl = (url) => {
  if (!url) return ''
  // 如果已经是完整URL或data URL，直接返回
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url
  }
  // 开发环境下使用 Vite 代理（/static 会自动代理到后端）
  // 生产环境需要拼接后端地址
  if (import.meta.env.DEV) {
    return url.startsWith('/') ? url : `/${url}`
  }
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  return `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`
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

// ── GSAP 按钮交互动画 ──────────────────────────────────────────────────────
const animateButton = (event, element) => {
  if (!element) return
  
  // 点击缩放动画
  gsap.to(element, {
    scale: 0.92,
    duration: 0.1,
    ease: 'power2.in',
    onComplete: () => {
      gsap.to(element, {
        scale: 1,
        duration: 0.4,
        ease: 'elastic.out(1.5, 0.3)'
      })
    }
  })
  
  // 波纹效果
  const rect = element.getBoundingClientRect()
  const ripple = document.createElement('span')
  ripple.style.cssText = `
    position: absolute;
    width: 20px;
    height: 20px;
    background: rgba(255,255,255,0.5);
    border-radius: 50%;
    pointer-events: none;
    left: ${event.clientX - rect.left - 10}px;
    top: ${event.clientY - rect.top - 10}px;
    transform: scale(0);
  `
  element.style.position = 'relative'
  element.style.overflow = 'hidden'
  element.appendChild(ripple)
  
  gsap.to(ripple, {
    scale: 15,
    opacity: 0,
    duration: 0.8,
    ease: 'power2.out',
    onComplete: () => ripple.remove()
  })
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

const deleteMsg = async (idx) => {
  const msg = messages.value[idx]
  if (!msg) return
  
  try {
    // 调用后端API删除消息
    if (msg.id && conversationId.value) {
      await conversationAPI.deleteMessage(conversationId.value, msg.id)
    }
    
    // 从前端列表中移除
    if (msg.role === 'user') {
      const next = messages.value[idx + 1]
      messages.value.splice(idx, next?.role === 'assistant' ? 2 : 1)
    } else {
      messages.value.splice(idx, 1)
    }
    
    showToast('消息已删除')
  } catch (err) {
    console.error('删除消息失败:', err)
    // 即使API失败，也从前端移除（降级处理）
    if (msg.role === 'user') {
      const next = messages.value[idx + 1]
      messages.value.splice(idx, next?.role === 'assistant' ? 2 : 1)
    } else {
      messages.value.splice(idx, 1)
    }
  }
  
  hoveredIdx.value = -1
  hideSelectionMenu()
}

// ── 选中文字操作菜单（类似豆包）─────────────────────────────────────
const selectionMenu = ref({ show: false, x: 0, y: 0, text: '', targetMsgIdx: null })

const showSelectionMenu = (event) => {
  // 阻止事件冒泡（避免立即被全局click关闭）
  event.stopPropagation()
  event.preventDefault()
  
  const selection = window.getSelection()
  const selectedText = selection.toString().trim()
  
  if (!selectedText || selectedText.length < 2) {
    hideSelectionMenu()
    return
  }
  
  // 找到选中的消息索引
  const bubbleEl = selection.anchorNode?.closest('.bubble')
  const msgRow = selection.anchorNode?.closest('.msg-row')
  
  if (!bubbleEl) {
    hideSelectionMenu()
    return
  }
  
  // 获取消息索引
  let msgIdx = -1
  if (msgRow) {
    const allRows = messagesArea.value?.querySelectorAll('.msg-row')
    if (allRows) {
      msgIdx = Array.from(allRows).indexOf(msgRow)
    }
  }
  
  const range = selection.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  
  // 计算菜单位置（确保不超出屏幕）
  let menuX = rect.left + rect.width / 2
  let menuY = rect.bottom + window.scrollY + 8
  
  // 防止超出右边界
  if (menuX + 150 > window.innerWidth) {
    menuX = window.innerWidth - 160
  }
  // 防止超出左边界
  if (menuX - 150 < 0) {
    menuX = 10
  }
  // 防止超出下边界
  if (menuY + 60 > window.innerHeight + window.scrollY) {
    menuY = rect.top + window.scrollY - 50
  }
  
  // 延迟显示（避免被click事件立即关闭）
  setTimeout(() => {
    selectionMenu.value = {
      show: true,
      x: menuX,
      y: menuY,
      text: selectedText,
      targetMsgIdx: msgIdx
    }
  }, 10)
}

const hideSelectionMenu = () => {
  selectionMenu.value.show = false
}

// 复制选中文字
const copySelectedText = async () => {
  if (!selectionMenu.value.text) return
  
  try {
    await navigator.clipboard.writeText(selectionMenu.value.text)
    showToast('📋 已复制到剪贴板')
  } catch (err) {
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = selectionMenu.value.text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    showToast('📋 已复制到剪贴板')
  }
  hideSelectionMenu()
}

// 朗读选中文字
const speakSelectedText = () => {
  if (!selectionMenu.value.text) return
  
  if (window.currentAudio) {
    window.currentAudio.pause()
    window.currentAudio.src = ''
    window.currentAudio = null
  }
  
  const utterance = new SpeechSynthesisUtterance(selectionMenu.value.text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  
  speechSynthesis.speak(utterance)
  hideSelectionMenu()
  showToast('🔊 开始朗读')
}

// 解释选中文字
const explainSelectedText = () => {
  if (!selectionMenu.value.text) return
  
  inputText.value = `请解释一下这段内容：\n"${selectionMenu.value.text}"`
  hideSelectionMenu()
  focusInput()
  sendMessage()
}

// 将选中的内容添加到对话
const addToConversation = () => {
  if (!selectionMenu.value.text) return
  
  inputText.value = selectionMenu.value.text
  hideSelectionMenu()
  focusInput()
  showToast('已添加到输入框')
}

// ── Markdown 渲染 ────────────────────────────────────────────────────
const renderMarkdown = (text) => {
  if (!text) return ''
  
  try {
    // 配置 marked 选项
    marked.setOptions({
      breaks: true,        // 支持换行
      gfm: true,          // 支持 GitHub 风格的 Markdown
      headerIds: false,   // 不生成标题ID
      mangle: false       // 不转义邮箱地址
    })
    
    return marked.parse(text)
  } catch (e) {
    console.error('Markdown 渲染失败:', e)
    return text.replace(/\n/g, '<br>')
  }
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

// ── 附件上传处理 ────────────────────────────────────────────────────────────────
const attachments = ref([])
const uploading = ref(false)

const handleFileUpload = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  
  const file = files[0]
  if (file.type.startsWith('image/') && file.size > 2 * 1024 * 1024) {
    showToast('为控制成本，图片大小不能超过 2MB')
    return
  }
  if (file.type.startsWith('video/') && file.size > 10 * 1024 * 1024) {
    showToast('为控制成本，视频大小不能超过 10MB')
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast('文件大小不能超过 10MB')
    return
  }
  
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await conversationAPI.uploadFile(formData)
    
    if (res.success) {
      attachments.value.push(res.data)
      showToast('附件添加成功')
    } else {
      showToast('上传失败')
    }
  } catch (err) {
    showToast('上传出错')
  } finally {
    uploading.value = false
    event.target.value = '' // 清除 input 状态
  }
}

const removeAttachment = (index) => {
  attachments.value.splice(index, 1)
}

// ── 发送消息 ──────────────────────────────────────────────────────────────────
const sendMessage = async () => {
  const text = inputText.value.trim()
  if ((!text && attachments.value.length === 0) || typing.value || uploading.value) return

  const fileUrls = attachments.value.map(a => a.url)
  const currentAttachments = [...attachments.value]

  messages.value.push({ role: 'user', content: text, file_urls: fileUrls, timestamp: new Date().toISOString() })
  
  // 清空输入区
  inputText.value = ''
  attachments.value = []
  
  if (inputRef.value) inputRef.value.style.height = 'auto'
  typing.value = true
  await scrollToBottom()

  try {
    // 使用流式输出（实时显示）
    let fullContent = ''
    let aiMsgIndex = -1  // 初始化为-1（还没创建消息）
    
    await conversationAPI.sendMessageStream(
      {
        digital_person_id: personId,
        message: text,
        conversation_id: conversationId.value,
        file_urls: fileUrls.length > 0 ? fileUrls : undefined,
      },
      // 每收到一个chunk就更新显示
      (chunk) => {
        fullContent += chunk
        
        // ✅ 第一个chunk到达时才创建AI消息（避免空白框）
        if (aiMsgIndex === -1) {
          aiMsgIndex = messages.value.length
          messages.value.push({
            role: 'assistant',
            content: chunk,  // 直接用第一个chunk的内容
            emotion: '',
            timestamp: new Date().toISOString(),
            isStreaming: true,
          })
          // 隐藏typing动画（因为已经有实际内容了）
          typing.value = false
        } else {
          // 后续chunk追加内容
          if (messages.value[aiMsgIndex]) {
            messages.value[aiMsgIndex].content = fullContent
          }
        }
        
        // 自动滚动到底部
        scrollToBottom()
      }
    )

    // 流式完成，更新消息状态
    if (aiMsgIndex !== -1 && messages.value[aiMsgIndex]) {
      messages.value[aiMsgIndex].content = fullContent
      messages.value[aiMsgIndex].isStreaming = false
    }

    // 获取对话ID和情绪（需要额外请求）
    // 注意：流式模式不返回这些信息，可以忽略或从后端获取
    
    // ✅ 每轮对话结束后自动刷新记忆列表
    await loadMemories()
    editState.value.active = false // 发送成功，确认放弃被替换的消息
    
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

// ── 粘贴上传处理（Ctrl+V 粘贴图片/视频自动上传）────────────────────────────
const handlePaste = async (event) => {
  const items = event.clipboardData?.items
  if (!items) return
  
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type.startsWith('image/') || item.type.startsWith('video/')) {
      const file = item.getAsFile()
      if (file) {
        // 文件大小校验
        if (file.type.startsWith('image/') && file.size > 2 * 1024 * 1024) {
          showToast('图片大小不能超过 2MB')
          return
        }
        if (file.type.startsWith('video/') && file.size > 10 * 1024 * 1024) {
          showToast('视频大小不能超过 10MB')
          return
        }
        
        uploading.value = true
        try {
          const formData = new FormData()
          formData.append('file', file)
          const res = await conversationAPI.uploadFile(formData)
          
          if (res.success) {
            attachments.value.push(res.data)
            showToast('✅ 已粘贴并添加附件')
          } else {
            showToast('上传失败')
          }
        } catch (err) {
          showToast('上传出错')
        } finally {
          uploading.value = false
        }
        
        // 阻止默认行为，避免粘贴到文本框
        event.preventDefault()
        break
      }
    }
  }
}

// ── Lightbox 图片/视频放大预览 ──────────────────────────────────────────────
const lightbox = reactive({
  show: false,
  url: '',
  type: '', // 'image' 或 'video'
  loading: true
})

const previewAttachment = (att) => {
  // 处理不同的输入格式
  let url = ''
  let type = ''
  
  if (typeof att === 'string') {
    // 如果传入的是字符串URL
    url = att
    type = att.match(/\.(mp4|mov|avi|webm)$/i) ? 'video' : 'image'
  } else if (att && att.url) {
    // 如果传入的是对象 { url, type }
    url = att.url
    type = att.type || (url.match(/\.(mp4|mov|avi|webm)$/i) ? 'video' : 'image')
  } else {
    console.error('previewAttachment: 无效的附件参数', att)
    return
  }
  
  // 使用 getFullUrl 确保URL完整
  url = getFullUrl(url)
  
  console.log('Lightbox 打开:', { url, type })
  
  // 设置状态
  lightbox.show = true
  lightbox.url = url
  lightbox.type = type
  lightbox.loading = true
  
  // 预加载图片/视频
  if (type === 'image') {
    const img = new Image()
    img.onload = () => { 
      console.log('图片加载完成')
      lightbox.loading = false 
    }
    img.onerror = (err) => { 
      console.error('图片加载失败', err)
      lightbox.loading = false 
      showToast('❌ 图片加载失败，请检查网络连接')
    }
    img.src = url
  } else {
    lightbox.loading = false
  }
  
  // 使用 nextTick 确保 DOM 更新后再执行动画
  nextTick(() => {
    const overlay = document.querySelector('.lightbox-overlay')
    const content = document.querySelector('.lightbox-content')
    
    if (overlay && content) {
      // GSAP 动画进入
      gsap.fromTo(overlay, 
        { opacity: 0 },
        { opacity: 1, duration: 0.3, ease: 'power2.out' }
      )
      gsap.fromTo(content,
        { scale: 0.8, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.4, ease: 'back.out(1.5)', delay: 0.1 }
      )
      
      // 聚焦到遮罩层以支持 ESC 关闭
      overlay.focus()
    } else {
      console.error('Lightbox DOM 元素未找到')
    }
  })
}

const closeLightbox = () => {
  gsap.to('.lightbox-content', {
    scale: 0.8,
    opacity: 0,
    rotationY: 15,
    duration: 0.25,
    ease: 'power2.in',
    onComplete: () => {
      lightbox.show = false
      lightbox.url = ''
      lightbox.type = ''
    }
  })
  gsap.to('.lightbox-overlay', {
    opacity: 0,
    duration: 0.25,
    ease: 'power2.in'
  })
}

// Lightbox 辅助方法
const downloadMedia = (url) => {
  const a = document.createElement('a')
  a.href = url
  a.download = url.split('/').pop() || 'download'
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

let zoomLevel = 1
const handleZoom = (event) => {
  event.deltaY < 0 ? (zoomLevel += 0.1) : (zoomLevel -= 0.1)
  zoomLevel = Math.max(0.5, Math.min(3, zoomLevel))
  
  const img = document.querySelector('.lightbox-image')
  if (img) {
    gsap.to(img, {
      scale: zoomLevel,
      duration: 0.3,
      ease: 'power2.out'
    })
  }
}

// ── 生命周期清除 ──────────────────────────────────────────────────────────────
onUnmounted(() => {
  // 切换路由离开组件时，安全停止后台仍在播放的音频
  if (window.currentAudio) {
    window.currentAudio.pause()
    window.currentAudio.src = ''
    window.currentAudio = null
  }
  // 移除粘贴监听
  document.removeEventListener('paste', handlePaste)
  // 移除选中菜单监听
  document.removeEventListener('click', hideSelectionMenu)
})

// ── 初始化 ────────────────────────────────────────────────────────────────────
onMounted(async () => {
  // 立即显示聊天界面（不等待数据加载完成）
  loading.value = false
  focusInput()
  
  // 添加全局粘贴监听（支持Ctrl+V粘贴图片/视频）
  document.addEventListener('paste', handlePaste)
  
  // 添加全局点击事件（隐藏选中菜单）
  document.addEventListener('click', hideSelectionMenu)
  // 加载数字人（后台加载，不阻塞UI）
  try {
    if (userStore.currentPerson?.id === personId) {
      person.value = userStore.currentPerson
    } else {
      const res = await digitalPersonAPI.get(personId)
      if (res.success) person.value = res.data
    }
  } catch (e) { console.error('加载数字人失败:', e) }

  // 加载历史对话（后台加载）
  try {
    const listRes = await conversationAPI.list()
    if (listRes.success && listRes.data.length > 0) {
      const conv = listRes.data.find(c => c.digital_person_id === personId)
      if (conv) {
        conversationId.value = conv.id
        const cvRes = await conversationAPI.get(conv.id)
        if (cvRes.success && cvRes.data.messages && cvRes.data.messages.length > 0) {
          messages.value = cvRes.data.messages
          
          // 数据加载完成后，最新消息从下往上弹出动画
          await nextTick()
          await scrollToBottom()
          
          const msgElements = messagesArea.value?.querySelectorAll('.msg-row')
          if (msgElements && msgElements.length > 0) {
            // 只对最后几条消息做从下往上的入场动画
            const recentMsgs = Array.from(msgElements).slice(-5)
            gsap.fromTo(recentMsgs.reverse(), 
              { 
                opacity: 0, 
                y: 30,
                scale: 0.96 
              },
              { 
                opacity: 1, 
                y: 0, 
                scale: 1,
                duration: 0.35,
                stagger: 0.08,
                ease: 'power2.out'
              }
            )
          }
        }
      }
    }
  } catch (e) { console.error('加载历史:', e) }

  // 加载记忆（后台加载，不阻塞）
  loadMemories().catch(e => console.error('加载记忆失败:', e))
})

// 监听消息变化，当有新消息时自动执行入场动画
watch(() => messages.value.length, async (newVal, oldVal) => {
  if (newVal > oldVal) {
    await nextTick()
    await scrollToBottom()
    
    // 获取最新加入的一条消息进行动画
    const messageElements = messagesArea.value?.querySelectorAll('.msg-row')
    if (messageElements && messageElements.length > 0) {
      const lastMsg = messageElements[messageElements.length - 1]
      
      // 强制设置初始状态（不使用opacity动画避免颜色变淡）
      gsap.set(lastMsg, { 
        y: 30, 
        scale: 0.96,
        opacity: 1  // 确保opacity始终为1
      })
      
      // 平滑入场动画（只使用transform）
      gsap.to(lastMsg, {
        y: 0,
        scale: 1,
        duration: 0.4,
        ease: 'power2.out',
        onComplete: () => {
          // 动画完成后清除所有内联样式，恢复CSS原始样式
          lastMsg.style.removeProperty('transform')
          lastMsg.style.removeProperty('opacity')
        }
      })
      
      // 气泡轻微高亮效果（使用CSS transition而非GSAP）
      const bubble = lastMsg.querySelector('.bubble')
      if (bubble) {
        bubble.style.transition = 'box-shadow 0.6s ease'
        bubble.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.3)'
        setTimeout(() => {
          bubble.style.boxShadow = ''
          bubble.style.transition = ''
        }, 600)
      }
    }
  }
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
  background: #1e3a8a;
  color: #ffffff;
  border-bottom-right-radius: 4px;
}

.bubble-user .bubble-text {
  color: #ffffff !important;
  font-weight: 700;
  font-size: 17px;
  line-height: 1.8;
}

/* 用户消息中所有Markdown元素强制亮色 */
.bubble-user .bubble-text :deep(p),
.bubble-user .bubble-text :deep(li),
.bubble-user .bubble-text :deep(span),
.bubble-user .bubble-text :deep(div) {
  color: #ffffff !important;
}

.bubble-user .bubble-text :deep(strong),
.bubble-user .bubble-text :deep(b) {
  color: #fef08a !important;
  font-weight: 700;
  background: rgba(254, 240, 138, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
}

.bubble-user .bubble-text :deep(h1),
.bubble-user .bubble-text :deep(h2),
.bubble-user .bubble-text :deep(h3),
.bubble-user .bubble-text :deep(h4) {
  color: #fef08a !important;
}

.bubble-user .bubble-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  color: #fef3c7 !important;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.bubble-user .bubble-text :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  color: #fef3c7 !important;
}

.bubble-user .bubble-text :deep(blockquote) {
  color: #e2e8f0 !important;
  border-left-color: #fef08a;
  background: rgba(255, 255, 255, 0.05);
}

.bubble-user .bubble-text :deep(a) {
  color: #93c5fd !important;
}

.bubble-user .bubble-time {
  color: rgba(255, 255, 255, 0.8) !important;
}

/* 用户消息中情绪标签亮色 */
.bubble-user .emotion-positive {
  color: #6ee7b7 !important;
  background: rgba(110, 231, 183, 0.15) !important;
}
.bubble-user .emotion-negative {
  color: #fca5a5 !important;
  background: rgba(252, 165, 165, 0.15) !important;
}
.bubble-user .emotion-neutral {
  color: #93c5fd !important;
  background: rgba(147, 197, 253, 0.15) !important;
}

.bubble-text { white-space: pre-wrap; word-break: break-word; }

.bubble-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

/* 情绪按钮（替代原来的静态标签） */
.emotion-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: none;
  border-radius: 12px;
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.2s ease;
  background: transparent;
}

.emotion-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* 积极情绪 - 绿色系 */
.emotion-positive {
  color: #059669;
  background: rgba(5, 150, 105, 0.1);
}
.emotion-positive:hover {
  background: rgba(5, 150, 105, 0.2);
}

/* 消极情绪 - 橙红色系 */
.emotion-negative {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
}
.emotion-negative:hover {
  background: rgba(220, 38, 38, 0.2);
}

/* 中性情绪 - 灰色系 */
.emotion-neutral {
  color: #6b7280;
  background: rgba(107, 114, 128, 0.1);
}
.emotion-neutral:hover {
  background: rgba(107, 114, 128, 0.2);
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

/* 附件按钮样式 */
.attachment-btn {
  position: relative;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.attachment-btn:hover {
  background: #f0fdf4 !important;
  border-color: #86efac !important;
  transform: scale(1.1);
}
.attachment-btn:active {
  transform: scale(0.95);
}

@keyframes bounceIn {
  from { opacity: 0; transform: scale(0.3); }
  to { opacity: 1; transform: scale(1); }
}

.cancel-edit-btn {
  color: #dc2626;
  font-weight: 700;
  font-size: 0.9rem;
}
.cancel-edit-btn:hover { background: #fee2e2; border-color: #fca5a5; }

.input-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.attachments-preview {
  display: flex;
  gap: 10px;
  padding: 10px 16px 0;
  flex-wrap: wrap;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border-radius: 12px 12px 0 0;
  margin-bottom: -4px;
}

.attachment-item {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--c-white);
  border: 2px solid var(--c-gray-200);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.attachment-item:hover {
  transform: translateY(-3px) scale(1.05);
  border-color: #6366f1;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.25);
}

.attachment-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.attachment-item:hover .attachment-thumb {
  transform: scale(1.08);
}

.video-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.attachment-type-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(8px);
}

.attachment-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  border: none;
  border-radius: 50%;
  font-size: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.attachment-remove:hover {
  background: rgba(0,0,0,0.8);
}

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

/* 附件渲染样式 */
.msg-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.msg-attachment-item {
  max-width: 100%;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  transition: all 0.3s ease;
}

.msg-attachment-item:hover {
  transform: scale(1.02);
  box-shadow: 0 6px 24px rgba(99, 102, 241, 0.25);
}

.msg-attachment-item:hover .msg-attachment-zoom {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}

.msg-img, .msg-video {
  max-width: 100%;
  max-height: 220px;
  display: block;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.msg-attachment-zoom {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0.8);
  width: 44px;
  height: 44px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.25s ease;
  backdrop-filter: blur(8px);
  pointer-events: none;
}

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

/* ── GSAP 增强动画样式 ─────────────────────────────────────────────── */

/* 按钮悬停发光效果 */
.voice-btn:hover,
.send-btn:hover,
.attachment-btn:hover {
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

/* 附件预览入场动画 */
.attachment-item {
  animation: attachmentPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes attachmentPop {
  0% { 
    transform: scale(0) rotate(-10deg); 
    opacity: 0; 
  }
  100% { 
    transform: scale(1) rotate(0deg); 
    opacity: 1; 
  }
}

/* 附件删除按钮动画 */
.attachment-remove {
  transition: all 0.2s ease;
}
.attachment-remove:hover {
  transform: scale(1.15) rotate(90deg);
}

/* 消息气泡悬浮效果 */
.msg-row-user .bubble-user:hover,
.msg-row-ai .bubble-ai:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  transition: all 0.3s ease;
}

/* 操作按钮显示动画 */
.msg-ops button {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.msg-ops button:hover {
  transform: translateY(-2px) scale(1.05);
}

/* Toast 弹窗增强 */
.toast {
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  animation: toastSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toast.show {
  animation: toastSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1),
             toastFadeOut 0.3s ease-in 2.2s forwards;
}

@keyframes toastSlideIn {
  from { 
    transform: translateX(-50%) translateY(20px); 
    opacity: 0;
    filter: blur(4px);
  }
  to { 
    transform: translateX(-50%) translateY(0); 
    opacity: 1;
    filter: blur(0);
  }
}

@keyframes toastFadeOut {
  to { 
    opacity: 0;
    transform: translateX(-50%) translateY(-10px);
  }
}

/* 侧边栏滑入增强 */
.side-panel.open {
  animation: panelSlideIn 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes panelSlideIn {
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 打字指示器增强 */
.typing-dot {
  background: linear-gradient(135deg, #6366f1, #a78bfa);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

/* 发送按钮加载旋转 */
.spinner {
  border-color: transparent;
  border-top-color: white;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 情绪胶囊动画 */
.emotion-pill {
  animation: emotionPop 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes emotionPop {
  0% { transform: scale(0); }
  100% { transform: scale(1); }
}

/* 视频播放巨幕动画 */
.video-presentation-overlay {
  animation: videoOverlayIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes videoOverlayIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.presentation-video {
  animation: videoGlow 3s ease-in-out infinite alternate;
}

@keyframes videoGlow {
  from {
    filter: brightness(1) drop-shadow(0 0 20px rgba(255, 255, 255, 0.3));
  }
  to {
    filter: brightness(1.1) drop-shadow(0 0 40px rgba(255, 255, 255, 0.5));
  }
}

/* ── Lightbox 图片/视频放大预览样式 ─────────────────────────────── */
.lightbox-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-container {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.lightbox-close {
  position: absolute;
  top: -40px;
  right: -10px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  z-index: 10;
  backdrop-filter: blur(8px);
}

.lightbox-close:hover {
  background: rgba(239, 68, 68, 0.9);
  transform: rotate(90deg) scale(1.15);
  box-shadow: 0 4px 20px rgba(239, 68, 68, 0.4);
}

.lightbox-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: white;
  font-size: 14px;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.lightbox-content {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.6), 0 0 60px rgba(99, 102, 241, 0.2);
}

.lightbox-image {
  max-width: 85vw;
  max-height: 80vh;
  object-fit: contain;
  display: block;
  cursor: zoom-in;
  user-select: none;
}

.lightbox-video {
  max-width: 85vw;
  max-height: 80vh;
  outline: none;
  border-radius: 12px;
}

.lightbox-toolbar {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.toolbar-btn {
  padding: 8px 18px;
  background: rgba(255, 255, 255, 0.15);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.25s ease;
  backdrop-filter: blur(8px);
}

.toolbar-btn:hover {
  background: rgba(99, 102, 241, 0.6);
  border-color: #6366f1;
  transform: translateY(-2px);
}

.toolbar-info {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

/* ── 选中文字操作菜单（类似豆包）─────────────────────── */
.selection-menu {
  position: fixed;
  z-index: 10000;
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  animation: selectionMenuIn 0.2s ease-out;
  transform: translateX(-50%);
}

@keyframes selectionMenuIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-8px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

.selection-menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.selection-menu-item:hover {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

/* ── Markdown 渲染样式 ────────────────────────────────── */
.bubble-text {
  line-height: 1.7;
  word-break: break-word;
}

.bubble-text :deep(p) {
  margin: 0 0 8px 0;
}

.bubble-text :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble-text :deep(strong),
.bubble-text :deep(b) {
  color: var(--c-primary, #6366f1);
  font-weight: 600;
  background: linear-gradient(120deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
  padding: 1px 4px;
  border-radius: 3px;
}

.bubble-text :deep(h1),
.bubble-text :deep(h2),
.bubble-text :deep(h3),
.bubble-text :deep(h4) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: #1f2937;
}

.bubble-text :deep(h1) { font-size: 1.3em; }
.bubble-text :deep(h2) { font-size: 1.15em; }
.bubble-text :deep(h3) { font-size: 1.05em; }

.bubble-text :deep(ul),
.bubble-text :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.bubble-text :deep(li) {
  margin: 4px 0;
  line-height: 1.6;
}

.bubble-text :deep(code) {
  background: #f3f4f6;
  color: #d946ef;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.9em;
}

.bubble-text :deep(pre) {
  background: #1f2937;
  color: #e5e7eb;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  font-size: 0.9em;
}

.bubble-text :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  border-radius: 0;
}

.bubble-text :deep(blockquote) {
  border-left: 4px solid #6366f1;
  padding: 8px 16px;
  margin: 12px 0;
  background: rgba(99, 102, 241, 0.05);
  border-radius: 0 8px 8px 0;
  color: #4b5563;
}

.bubble-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.bubble-text :deep(th),
.bubble-text :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  text-align: left;
}

.bubble-text :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}

.bubble-text :deep(hr) {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, #e5e7eb, transparent);
  margin: 16px 0;
}

.bubble-text :deep(a) {
  color: #6366f1;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}

.bubble-text :deep(a:hover) {
  border-bottom-color: #6366f1;
}

/* ── 情绪分析弹窗样式 ─────────────────────────────── */
.emotion-modal-overlay {
  z-index: 10001;
}

.emotion-analysis-modal {
  max-width: 400px;
  padding: 24px;
}

.emotion-analysis-modal h3 {
  margin-bottom: 20px;
  font-size: 1.2rem;
  color: #1f2937;
}

/* 情绪展示区 */
.emotion-display {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 20px;
}

.emotion-display-positive {
  background: linear-gradient(135deg, rgba(5, 150, 105, 0.1) 0%, rgba(16, 185, 129, 0.15) 100%);
  border: 1px solid rgba(5, 150, 105, 0.2);
}

.emotion-display-negative {
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.1) 0%, rgba(239, 68, 68, 0.15) 100%);
  border: 1px solid rgba(220, 38, 38, 0.2);
}

.emotion-display-neutral {
  background: linear-gradient(135deg, rgba(107, 114, 128, 0.1) 0%, rgba(156, 163, 175, 0.15) 100%);
  border: 1px solid rgba(107, 114, 128, 0.2);
}

.emotion-big-icon {
  font-size: 3rem;
  line-height: 1;
}

.emotion-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.emotion-name {
  font-size: 1.3rem;
  font-weight: 600;
  color: #1f2937;
}

.emotion-level {
  font-size: 0.85rem;
  color: #6b7280;
}

/* 情绪建议 */
.emotion-suggestions {
  margin-bottom: 20px;
}

.emotion-suggestions h4 {
  font-size: 0.95rem;
  color: #374151;
  margin-bottom: 12px;
}

.emotion-suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.emotion-suggestions li {
  padding: 8px 12px;
  margin-bottom: 6px;
  background: #f9fafb;
  border-radius: 8px;
  font-size: 0.88rem;
  color: #4b5563;
  display: flex;
  align-items: center;
  gap: 8px;
}

.emotion-suggestions li::before {
  content: '✓';
  color: #6366f1;
  font-weight: bold;
}

/* 情绪操作按钮 */
.emotion-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>

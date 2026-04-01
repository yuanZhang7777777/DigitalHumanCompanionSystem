<template>
  <div class="create-page">
    <!-- 顶部导航 -->
    <header class="app-header">
      <div class="container">
        <button class="btn btn-ghost btn-sm" @click="router.push('/home')">
          ← 返回
        </button>
        <h2 class="create-page-title">{{ isEditing ? '编辑数字伙伴' : '创建数字伙伴' }}</h2>
        <div style="width:80px"></div>
      </div>
    </header>

    <div class="create-layout container">
      <!-- 左侧：实时预览 -->
      <aside class="preview-panel animate-fade-up">
        <div class="preview-sticky clean-pane">
          <p class="preview-label">实时预览</p>

          <!-- 头像 -->
          <div class="preview-avatar-wrap">
            <label class="avatar-label">
              <div class="preview-avatar">
                <img v-if="avatarPreview" :src="avatarPreview" class="avatar-img" :alt="form.name" />
                <span v-else class="avatar-initials">{{ form.name?.[0] || '?' }}</span>
              </div>
              <input type="file" accept="image/*" class="hidden-input" @change="onAvatarChange" />
            </label>
            <span class="avatar-hint">点击上传头像</span>
          </div>

          <h3 class="preview-name">{{ form.name || '数字伙伴' }}</h3>
          <div class="preview-relation-wrap">
            <span class="tag preview-relation">{{ form.relationship || '关系未设置' }}</span>
          </div>

          <!-- 性格标签预览 -->
          <div v-if="form.personality_traits.length" class="preview-tags">
            <span v-for="t in form.personality_traits" :key="t" class="tag">{{ t }}</span>
          </div>

          <p v-if="form.background_story" class="preview-story">
            {{ form.background_story.slice(0, 100) }}{{ form.background_story.length > 100 ? '…' : '' }}
          </p>

          <div v-if="form.experiences.length" class="preview-timeline">
            <p class="preview-sub-label">经历时间线</p>
            <div v-for="(exp, i) in form.experiences" :key="i" class="timeline-item">
              <span class="timeline-year">{{ exp.year }}</span>
              <span class="timeline-event">{{ exp.event }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：表单 -->
      <main class="form-panel">
        <form @submit.prevent="handleSubmit" novalidate>

          <!-- 错误提示 -->
          <div v-if="errorMsg" class="error-banner animate-scale-in">{{ errorMsg }}</div>

          <!-- ── 基本信息 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">基本信息</h3>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">名字 *</label>
                <input v-model="form.name" class="form-input" type="text" placeholder="例如：小林" maxlength="20" />
              </div>
              <div class="form-group">
                <label class="form-label">与你的关系 *</label>
                <input v-model="form.relationship" class="form-input" type="text" placeholder="例如：导师、挚友" maxlength="20" />
              </div>
            </div>
          </section>

          <!-- ── 专属动态视频上传 ── -->
          <section v-if="isEditing" class="form-section clean-pane animate-fade-up" style="border: 1px solid var(--c-primary); background: rgba(56,189,248,0.02)">
            <h3 class="section-title" style="color: var(--c-primary)">🎬 专属动态视频</h3>
            <p class="section-desc">上传一段此角色的短视频（MP4），在聊天朗读时会自动播放。手动上传可永久保存且节省生成费用。</p>
            
            <div class="video-upload-area">
              <div v-if="form.speaking_video_url" class="video-preview-wrap">
                <video :src="form.speaking_video_url" controls class="video-preview-player"></video>
                <p class="video-url-hint">当前视频已保存至云端</p>
              </div>
              
              <div class="video-upload-ops">
                <input 
                  type="file" 
                  ref="videoInputRef" 
                  @change="handleVideoUpload" 
                  accept="video/mp4,video/x-m4v,video/*" 
                  style="display:none" 
                />
                <button 
                  type="button" 
                  class="btn btn-secondary" 
                  style="width: 100%; display:flex; justify-content:center; gap:8px;"
                  @click="triggerVideoUpload"
                  :disabled="uploadingVideo"
                >
                  <span v-if="uploadingVideo" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:var(--c-primary)"></span>
                  {{ uploadingVideo ? '正在上传视频到 OSS...' : (form.speaking_video_url ? '重新上传视频' : '点此上传角色视频 (MP4)') }}
                </button>
              </div>
            </div>
          </section>

          <!-- ── 性格标签 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">性格特征</h3>
            <p class="section-desc">点击预设标签快速选择，也可输入自定义标签（无数量限制）</p>

            <!-- 已选标签 -->
            <div v-if="form.personality_traits.length" class="selected-tags">
              <span
                v-for="(t, i) in form.personality_traits"
                :key="i"
                class="tag tag-filled tag-removable"
                @click="removeTrait(i)"
                title="点击移除"
              >
                {{ t }} ×
              </span>
            </div>

            <!-- 预设标签 -->
            <div class="preset-tags">
              <button
                v-for="t in PRESET_TRAITS"
                :key="t"
                type="button"
                class="tag preset-tag"
                :class="{ 'tag-filled': form.personality_traits.includes(t) }"
                @click="togglePreset(t)"
              >{{ t }}</button>
            </div>

            <!-- 自定义输入 -->
            <div class="custom-tag-input">
              <input
                v-model="customTag"
                class="form-input"
                type="text"
                placeholder="输入自定义标签，按 Enter 添加"
                @keydown.enter.prevent="addCustomTag"
              />
              <button type="button" class="btn btn-secondary btn-sm" @click="addCustomTag">添加</button>
            </div>
          </section>

          <!-- ── 背景故事 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">背景故事</h3>
            <p class="section-desc">描述这位数字伙伴的过往和身份，AI 在对话中会融入这些背景</p>
            <textarea
              v-model="form.background_story"
              class="form-textarea"
              rows="5"
              placeholder="例如：我是一名有 12 年经验的 HR，当年也是普通二本毕业..."
            ></textarea>
          </section>

          <!-- ── 说话风格 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">说话风格</h3>
            <p class="section-desc">告诉 AI 用什么语气和方式说话</p>
            <input
              v-model="form.speaking_style"
              class="form-input"
              type="text"
              placeholder="例如：直接简洁，不说废话，偶尔用幽默缓解气氛"
            />
          </section>

          <!-- ── 补充描述 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">补充描述</h3>
            <textarea
              v-model="form.user_description"
              class="form-textarea"
              rows="3"
              placeholder="其他你想让 AI 知道的特点，例如价值观、禁忌话题等"
            ></textarea>
          </section>

          <!-- ── 音视频智能提取 (AI Extractions) ── -->
          <section class="form-section clean-pane highlight-section" style="margin-top: 24px; border: 1px dashed var(--c-google-blue); background: var(--c-google-blue-light)">
            <h3 class="section-title" style="color: var(--c-google-blue)">✨ 智能记忆链提取</h3>
            <p class="section-desc">上传此人的采访、脱口秀音频或视频短片，AI 将为您瞬间提取他/她的「核心性格」与「重要人生经历」。</p>
            
            <div style="margin-top: 12px">
              <input 
                type="file" 
                ref="mediaInputRef" 
                @change="handleMediaUpload" 
                accept="audio/*,video/*" 
                style="display:none" 
              />
              <button 
                type="button" 
                class="btn btn-secondary btn-full" 
                style="border-color: var(--c-primary); color: var(--c-primary); display:flex; justify-content:center; gap:8px;"
                @click="triggerMediaUpload"
                :disabled="extractingMedia"
              >
                <span v-if="extractingMedia" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:var(--c-primary)"></span>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                {{ extractingMedia ? '正在分析提取音视频内容，请耐心等待 (约需1-3分钟)...' : '🎬 / 🎤 点击上传音视频一键分析' }}
              </button>
            </div>
          </section>

          <!-- ── 经历时间线 ── -->
          <section class="form-section clean-pane">
            <h3 class="section-title">人生经历时间线</h3>
            <p class="section-desc">添加关键经历，AI 会在对话中自然地联系这些经历</p>

            <div v-for="(exp, i) in form.experiences" :key="i" class="experience-item">
              <input
                v-model="exp.year"
                class="form-input exp-year"
                type="text"
                placeholder="年份"
              />
              <input
                v-model="exp.event"
                class="form-input exp-event"
                type="text"
                placeholder="发生的事情，例如：三年业绩全公司第一"
              />
              <button type="button" class="btn btn-ghost btn-icon" @click="removeExperience(i)" title="移除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <button type="button" class="btn btn-secondary btn-sm" @click="addExperience">
              + 添加经历
            </button>
          </section>

          <!-- ── 音色个性化 (GPT-SoVITS 配置) ── -->
          <section class="form-section clean-pane animate-fade-up delay-6" style="margin-top:24px">
            <h3 class="section-title">🔊 音色个性化 (GPT-SoVITS 专属配置)</h3>
            <p class="section-desc">若留空则使用默认配置。可输入您自己在本地训练好的模型路径，让数字人使用完美克隆的专属声音。</p>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">GPT 模型路径</label>
                <input v-model="form.tts_config.gpt_weights" type="text" class="form-input" placeholder="例: GPT_weights_v2ProPlus/xxx.ckpt" />
              </div>
              <div class="form-group">
                <label class="form-label">SoVITS 模型路径</label>
                <input v-model="form.tts_config.sovits_weights" type="text" class="form-input" placeholder="例: SoVITS_weights_v2ProPlus/xxx.pth" />
              </div>
            </div>
            <div class="form-group" style="margin-top:12px">
              <label class="form-label">参考音频路径</label>
              <input v-model="form.tts_config.ref_audio_path" type="text" class="form-input" placeholder="例: refer.wav (需放在相应的路径下)" />
            </div>
            <div class="form-row" style="margin-top:12px">
              <div class="form-group" style="flex:2">
                <label class="form-label">参考音频文本</label>
                <input v-model="form.tts_config.prompt_text" type="text" class="form-input" placeholder="写入参考音频的文字内容" />
              </div>
              <div class="form-group" style="flex:1">
                <label class="form-label">语言</label>
                <select v-model="form.tts_config.prompt_lang" class="form-input">
                  <option value="zh">中文</option>
                  <option value="en">英文</option>
                  <option value="ja">日文</option>
                </select>
              </div>
            </div>
          </section>

          <!-- ── 提交 ── -->
          <div class="form-submit">
            <button type="button" class="btn btn-secondary" @click="router.push('/home')">取消</button>
            <button
              type="submit"
              class="btn btn-primary"
              :class="{ 'btn-loading': submitting }"
            >
              <span v-if="submitting" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:#fff"></span>
              <span v-else>{{ isEditing ? '保存修改' : '创建伙伴' }}</span>
            </button>
          </div>
        </form>
      </main>
    </div>

    <!-- Toast -->
    <div class="toast" :class="{ show: toast.show }">{{ toast.msg }}</div>

    <!-- ── 提取结果选择弹窗 (Extraction Modal) ── -->
    <div v-if="showExtractionModal" class="extraction-modal-overlay">
      <div class="extraction-modal-content animate-scale-in clean-pane">
        <div class="modal-header">
          <h3 style="font-size:1.1rem; font-weight:700">✨ AI 提取分析完毕</h3>
          <p style="font-size:0.8rem; color:var(--c-gray-400); margin-top:4px">请勾选您想保存到数字人档案中的信息</p>
        </div>
        
        <div class="modal-body">
          <div v-for="(speaker, sIdx) in extractionResult.speakers" :key="sIdx" class="speaker-section">
            <h3 class="speaker-title">👤 角色/发音人: <span style="color:var(--c-primary)">{{ speaker.role }}</span></h3>
            
            <div class="extract-grid">
              <!-- 左侧性格 -->
              <div class="extract-col">
                <h4 class="extract-subtitle">🎭 发现的性格特征</h4>
                <div class="extract-list">
                  <label v-for="(trait, idx) in speaker.personality_traits" :key="idx" class="extract-check-row">
                    <input type="checkbox" v-model="trait.selected" class="check-input"/>
                    <span class="tag">{{ trait.value }}</span>
                  </label>
                  <div v-if="!speaker.personality_traits?.length" class="empty-hint">未能提取出明显性格描述</div>
                </div>
              </div>
              
              <!-- 右侧经历 -->
              <div class="extract-col">
                <h4 class="extract-subtitle">⏱️ 提取的关键经历</h4>
                <div class="extract-list">
                  <label v-for="(exp, idx) in speaker.experiences" :key="idx" class="extract-check-row">
                    <input type="checkbox" v-model="exp.selected" class="check-input"/>
                    <div class="exp-preview">
                      <span class="exp-year-badge">{{ exp.year }}</span>
                      <span class="exp-event-text">{{ exp.event }}</span>
                    </div>
                  </label>
                  <div v-if="!speaker.experiences?.length" class="empty-hint">未能提取出具体事件经历</div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!extractionResult.speakers?.length" class="empty-hint" style="text-align:center; padding: 2rem 0;">未能从音视频中分析出具体的发音人或经历</div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showExtractionModal = false">取消放弃</button>
          <button class="btn btn-primary" @click="applyExtraction">立即导入所选内容</button>
        </div>
      </div>
    </div>
    
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { useUserStore } from '../stores/user'
import { digitalPersonAPI } from '../api'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 预设性格标签
const PRESET_TRAITS = ['温柔体贴', '理性冷静', '幽默风趣', '认真负责', '乐观开朗', '直率坦诚', '耐心细致', '经验丰富', '务实接地气', '善于倾听', '充满活力', '沉稳可靠']

const isEditing = ref(false)
const editId = ref(null)
const submitting = ref(false)
const errorMsg = ref('')
const customTag = ref('')
const avatarPreview = ref(null)
const toast = ref({ show: false, msg: '' })

const form = reactive({
  name: '',
  relationship: '',
  personality_traits: [],
  background_story: '',
  speaking_style: '',
  user_description: '',
  avatar: null,
  tts_config: { gpt_weights: '', sovits_weights: '', ref_audio_path: '', prompt_text: '', prompt_lang: 'zh' },
  experiences: [],
  speaking_video_url: null,
})

// ── 视频上传状态 ──
const videoInputRef = ref(null)
const uploadingVideo = ref(false)

const triggerVideoUpload = () => {
  videoInputRef.value?.click()
}

const handleVideoUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > 50 * 1024 * 1024) {
    message.error('视频文件不能超过 50MB')
    return
  }

  uploadingVideo.value = true
  const hideLoading = message.loading('🚀 正在上传视频到您的 OSS 存储...', 0)
  
  const formData = new FormData()
  formData.append('video', file)
  
  try {
    const res = await digitalPersonAPI.uploadVideo(editId.value, formData)
    hideLoading()
    if (res.success) {
      form.speaking_video_url = res.data.video_url
      message.success('视频上传并保存成功！')
    } else {
      message.error(res.message || '视频上传失败')
    }
  } catch (err) {
    hideLoading()
    message.error('视频上传失败，请检查网络或 OSS 配置')
  } finally {
    uploadingVideo.value = false
    e.target.value = ''
  }
}

// ── 音视频提取状态 ──
const mediaInputRef = ref(null)
const extractingMedia = ref(false)
const showExtractionModal = ref(false)
const extractionResult = reactive({
  speakers: []
})

const triggerMediaUpload = () => {
  mediaInputRef.value?.click()
}

const handleMediaUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  
  // 重置 Input，允许重复传相同文件
  e.target.value = ''
  
  extractingMedia.value = true
  errorMsg.value = ''
  
  const hideLoading = message.loading('🚀 正在上传并由 AI 分析音视频内容，这可能需要 1~3 分钟，请耐心等待千万不要刷新页面...', 0)
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const res = await digitalPersonAPI.extractMedia(formData)
    hideLoading()
    if (res.success && res.data) {
      // 包装数据结构用于选择 Checkbox (支持多角色)
      extractionResult.speakers = (res.data.speakers || []).map(spk => {
        return {
          role: spk.role || "未知角色",
          personality_traits: (spk.personality_traits || []).map(t => ({ value: t, selected: true })),
          experiences: (spk.experiences || []).map(exp => ({ ...exp, selected: true }))
        }
      })
      
      showExtractionModal.value = true
      message.success('🎉 智能提取成功！请在弹窗中勾选需要导入的信息')
    } else {
      errorMsg.value = res.message || '提取过程发生未知错误'
      message.error(errorMsg.value)
    }
  } catch (err) {
    hideLoading()
    errorMsg.value = err?.message || '媒体解析失败，请检查音视频格式或网络连接'
    message.error(errorMsg.value)
  } finally {
    extractingMedia.value = false
  }
}

const applyExtraction = () => {
  const selectedTraits = []
  const selectedExps = []
  
  extractionResult.speakers.forEach(speaker => {
    selectedTraits.push(...speaker.personality_traits.filter(t => t.selected).map(t => t.value))
    selectedExps.push(...speaker.experiences.filter(exp => exp.selected).map(exp => ({ year: exp.year, event: exp.event, type: exp.type || 'other'})))
  })
  
  // 合并性格
  selectedTraits.forEach(t => {
    if (!form.personality_traits.includes(t)) {
      form.personality_traits.push(t)
    }
  })
  
  // 合并经历
  form.experiences.push(...selectedExps)
  
  showExtractionModal.value = false
  showToast('导入成功')
}

// ── 头像 ──
const onAvatarChange = (e) => {
  const file = e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    avatarPreview.value = ev.target.result
    form.avatar = ev.target.result
  }
  reader.readAsDataURL(file)
}

// ── 性格标签 ──
const togglePreset = (t) => {
  const idx = form.personality_traits.indexOf(t)
  if (idx >= 0) form.personality_traits.splice(idx, 1)
  else form.personality_traits.push(t)
}

const removeTrait = (i) => {
  form.personality_traits.splice(i, 1)
}

const addCustomTag = () => {
  const t = customTag.value.trim()
  if (!t) return
  if (!form.personality_traits.includes(t)) {
    form.personality_traits.push(t)
  }
  customTag.value = ''
}

// ── 经历 ──
const addExperience = () => {
  form.experiences.push({ year: '', event: '', type: 'career' })
}

const removeExperience = (i) => {
  form.experiences.splice(i, 1)
}

// ── 提交 ──
const handleSubmit = async () => {
  errorMsg.value = ''
  if (!form.name.trim()) { errorMsg.value = '请输入名字'; return }
  if (!form.relationship.trim()) { errorMsg.value = '请输入与你的关系'; return }

  submitting.value = true
  try {
    let res
    if (isEditing.value) {
      res = await digitalPersonAPI.update(editId.value, { ...form })
    } else {
      res = await userStore.createDigitalPerson({ ...form })
    }

    if (res.success) {
      showToast(isEditing.value ? '已保存修改！' : '创建成功！')
      setTimeout(() => router.push('/home'), 800)
    } else {
      errorMsg.value = res.message || '操作失败，请重试'
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || err.message || '操作失败'
  } finally {
    submitting.value = false
  }
}

// ── Toast ──
const showToast = (msg) => {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 2000)
}

// ── 编辑模式：加载已有数据 ──
onMounted(async () => {
  const editPersonId = route.query?.edit
  if (editPersonId) {
    isEditing.value = true
    editId.value = editPersonId
    try {
      const res = await digitalPersonAPI.get(editPersonId)
      if (res.success) {
        const d = res.data
        form.name = d.name || ''
        form.relationship = d.relationship || ''
        form.personality_traits = [...(d.personality_traits || [])]
        form.background_story = d.background_story || ''
        form.speaking_style = d.speaking_style || ''
        form.user_description = d.user_description || ''
        form.avatar = d.avatar || null
        form.tts_config = Object.assign({ gpt_weights: '', sovits_weights: '', ref_audio_path: '', prompt_text: '', prompt_lang: 'zh' }, d.tts_config || {})
        form.experiences = [...(d.experiences || [])]
        form.speaking_video_url = d.speaking_video_url || null
        if (d.avatar) avatarPreview.value = d.avatar
      }
    } catch (e) {
      console.error('加载编辑数据失败', e)
    }
  }
})
</script>

<style scoped>
.create-page {
  min-height: 100vh;
  background: transparent;
}

.create-page-title {
  font-size: 1.125rem;
  font-weight: 500;
  color: var(--c-black);
}

/* 双栏布局 */
.create-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: var(--space-12);
  padding-top: var(--space-10);
  padding-bottom: var(--space-20);
  align-items: start;
}

@media (max-width: 900px) {
  .create-layout { grid-template-columns: 1fr; }
  .preview-panel { display: none; }
}

/* 左侧预览 */
.preview-panel {
  position: sticky;
  top: 72px;
}

.preview-sticky {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  /* clean-pane 类已提供样式 */
}

.preview-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--c-gray-400);
}

/* 头像 */
.preview-avatar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.avatar-label { cursor: pointer; }

.preview-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 1px solid var(--c-gray-100);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-gray-100);
  transition: border-color var(--dur-fast);
}
.avatar-label:hover .preview-avatar { border-color: var(--c-gray-400); }

.avatar-img { width: 100%; height: 100%; object-fit: cover; }

.avatar-initials {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--c-black);
}

.avatar-hint {
  font-size: 0.7rem;
  color: var(--c-gray-400);
}

.hidden-input { display: none; }

.preview-name {
  font-size: 1.25rem;
  font-weight: 500;
  color: var(--c-black);
  text-align: center;
}

.preview-relation-wrap {
  display: flex;
  justify-content: center;
}

.preview-relation { 
  display: inline-flex; 
  background: var(--c-google-blue-light);
  color: var(--c-google-blue);
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.preview-story {
  font-size: 0.8rem;
  color: var(--c-gray-500);
  line-height: 1.6;
}

.preview-sub-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-gray-400);
  margin-bottom: var(--space-2);
}

.preview-timeline {
  border-top: var(--border);
  padding-top: var(--space-4);
}

.timeline-item {
  display: flex;
  gap: var(--space-2);
  font-size: 0.75rem;
  color: var(--c-gray-600);
  line-height: 1.5;
  margin-bottom: var(--space-1);
}

.timeline-year {
  font-weight: 600;
  color: var(--c-black);
  white-space: nowrap;
}

/* 右侧表单 */
.form-panel { padding-top: 4px; }

.form-section {
  padding: var(--space-6);
  margin-bottom: var(--space-5);
  /* clean-pane 类已提供样式 */
}

.section-title {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--c-black);
  margin-bottom: var(--space-1);
}

.section-desc {
  font-size: 0.8rem;
  color: var(--c-gray-400);
  margin-bottom: var(--space-4);
  line-height: 1.5;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

@media (max-width: 600px) {
  .form-row { grid-template-columns: 1fr; }
}

/* 性格标签 */
.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--c-gray-50);
  border-radius: var(--radius-md);
  min-height: 44px;
}

.preset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.preset-tag {
  cursor: pointer;
  transition: all var(--dur-fast);
}

.custom-tag-input {
  display: flex;
  gap: var(--space-2);
}

.custom-tag-input .form-input { flex: 1; }

/* 经历时间线 */
.experience-item {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-3);
}

.exp-year {
  width: 90px;
  flex-shrink: 0;
}

.exp-event { flex: 1; }

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

/* 提交区域 */
.form-submit {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding-top: var(--space-4);
}

.add-exp-btn:hover { background: var(--c-gray-100); }

/* 专属动态视频上传 */
.video-upload-area {
  padding: var(--space-4);
  background: var(--c-white);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.video-preview-wrap {
  width: 100%;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--c-black);
  aspect-ratio: 16/9;
  display: flex;
  flex-direction: column;
}

.video-preview-player {
  width: 100%;
  flex: 1;
  object-fit: contain;
}

.video-url-hint {
  font-size: 0.75rem;
  color: var(--c-gray-400);
  text-align: center;
  padding: var(--space-2);
  background: var(--c-gray-50);
}

.video-upload-ops {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

/* --- 提取弹窗 Modal 样式 --- */
.extraction-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.extraction-modal-content {
  width: 90%;
  max-width: 700px;
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  max-height: 85vh;
  box-shadow: var(--shadow-xl);
}

.modal-header {
  padding: var(--space-6);
  border-bottom: var(--border);
}

.modal-body {
  padding: var(--space-6);
  overflow-y: auto;
}

.extract-grid {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: var(--space-6);
}

@media (max-width: 600px) {
  .extract-grid { grid-template-columns: 1fr; }
}

.extract-subtitle {
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: var(--space-4);
  color: var(--c-gray-800);
}

.extract-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.extract-check-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  cursor: pointer;
  padding: var(--space-3);
  background: var(--c-gray-50);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--dur-fast);
}

.extract-check-row:hover {
  background: var(--c-gray-100);
  border-color: var(--c-gray-200);
}

.exp-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.exp-year-badge {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--c-primary);
  background: rgba(56,189,248,0.1);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  display: inline-block;
  width: fit-content;
}
.exp-event-text {
  font-size: 0.85rem;
  line-height: 1.4;
  color: var(--c-gray-700);
}

.empty-hint {
  font-size: 0.8rem;
  color: var(--c-gray-400);
  font-style: italic;
  padding: var(--space-4);
  text-align: center;
  background: var(--c-gray-50);
  border-radius: var(--radius-md);
}

.modal-footer {
  padding: var(--space-4) var(--space-6);
  border-top: var(--border);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
</style>
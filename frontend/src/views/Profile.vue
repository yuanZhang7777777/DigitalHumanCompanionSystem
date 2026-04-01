<template>
  <div class="profile-page">
    <!-- 顶部导航 -->
    <header class="app-header">
      <div class="container">
        <button class="btn btn-ghost btn-sm" @click="$router.push('/home')">← 返回</button>
        <h2 class="profile-page-title">职业档案</h2>
      </div>
    </header>

    <div class="profile-layout container">
      <!-- 左侧：简历解析 -->
      <aside class="resume-panel animate-fade-up">
        <div class="section-box clean-pane">
          <h3 class="section-title">AI 简历解析</h3>
          <p class="section-desc">粘贴简历文本，AI 自动提取技能和经历（不支持 PDF，请复制文字内容）</p>
          <textarea
            v-model="resumeText"
            class="form-textarea"
            rows="10"
            placeholder="粘贴你的简历内容…"
          ></textarea>
          <button
            class="btn btn-primary btn-full"
            style="margin-top:12px"
            :class="{ 'btn-loading': parseLoading }"
            @click="handleParseResume"
            :disabled="parseLoading || !resumeText.trim()"
          >
            <span v-if="parseLoading" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:#fff"></span>
            <span v-else>🤖 AI 解析</span>
          </button>
          <div v-if="parseMsg" class="msg-bar" :class="parseMsgType" style="margin-top:10px">{{ parseMsg }}</div>

          <!-- 解析结果 -->
          <div v-if="parseResult" class="parse-result animate-scale-in">
            <p class="parse-result-title">✅ 解析结果</p>
            <div v-if="parseResult.skills?.length" class="parse-row">
              <span class="parse-label">技能</span>
              <div class="flex" style="flex-wrap:wrap;gap:6px">
                <span v-for="s in parseResult.skills" :key="s" class="tag">{{ s }}</span>
              </div>
            </div>
            <div v-if="parseResult.education" class="parse-row">
              <span class="parse-label">学历</span>
              <span class="parse-value">{{ parseResult.education }}</span>
            </div>
            <div v-if="parseResult.major" class="parse-row">
              <span class="parse-label">专业</span>
              <span class="parse-value">{{ parseResult.major }}</span>
            </div>
            <button class="btn btn-secondary btn-sm" @click="applyParseResult">✓ 应用到档案</button>
          </div>
        </div>
      </aside>

      <!-- 右侧：档案编辑 -->
      <main class="profile-form-panel">
        <div v-if="pageLoading" class="loading-state">
          <div class="spinner"></div>
        </div>

        <form v-else @submit.prevent="handleSave" novalidate>
          <!-- ── 技能 ── -->
          <section class="section-box clean-pane animate-fade-up">
            <h3 class="section-title">技能清单</h3>
            <div v-if="form.skills.length" class="skills-list">
              <span
                v-for="(s, idx) in form.skills"
                :key="idx"
                class="tag tag-removable tag-filled"
                @click="removeSkill(idx)"
                title="点击移除"
              >{{ s }} ×</span>
            </div>
            <div class="add-row" style="margin-top:12px">
              <input
                v-model="newSkill"
                class="form-input"
                placeholder="添加技能（如 Python、Excel…）按 Enter"
                @keydown.enter.prevent="addSkill"
              />
              <button type="button" class="btn btn-secondary btn-sm" @click="addSkill">添加</button>
            </div>
          </section>

          <!-- ── 教育背景 ── -->
          <section class="section-box clean-pane animate-fade-up delay-1">
            <h3 class="section-title">教育背景</h3>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">学历</label>
                <select v-model="form.education" class="form-input">
                  <option value="">请选择</option>
                  <option value="专科">专科</option>
                  <option value="本科">本科</option>
                  <option value="硕士">硕士</option>
                  <option value="博士">博士</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">专业</label>
                <input v-model="form.major" class="form-input" placeholder="你的专业方向" />
              </div>
            </div>
            <div class="form-group" style="margin-top:12px">
              <label class="form-label">实习/工作经历描述</label>
              <textarea v-model="form.experience_summary" class="form-textarea" rows="3" placeholder="简要描述你的实习或工作经历…"></textarea>
            </div>
          </section>

          <!-- ── 求职偏好 ── -->
          <section class="section-box clean-pane animate-fade-up delay-2">
            <h3 class="section-title">求职偏好</h3>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">期望月薪范围（元）</label>
                <div class="salary-row">
                  <input v-model.number="form.expected_salary_min" type="number" class="form-input" placeholder="最低" min="0" step="500" />
                  <span class="salary-sep">—</span>
                  <input v-model.number="form.expected_salary_max" type="number" class="form-input" placeholder="最高" min="0" step="500" />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">工作年限</label>
                <select v-model="form.experience_years" class="form-input">
                  <option value="">请选择</option>
                  <option value="应届">应届毕业生</option>
                  <option value="1">1年以下</option>
                  <option value="3">1-3年</option>
                  <option value="5">3-5年</option>
                  <option value="10">5年以上</option>
                </select>
              </div>
            </div>
            <div class="form-group" style="margin-top:12px">
              <label class="form-label">期望城市（逗号分隔）</label>
              <input v-model="locationsStr" class="form-input" placeholder="如：上海, 北京, 杭州" />
            </div>
            <label class="check-label" style="margin-top:12px">
              <input v-model="form.is_fresh_graduate" type="checkbox" class="check-input" />
              <span>我是应届生 / 即将毕业</span>
            </label>
          </section>

          <!-- ── 自我描述 ── -->
          <section class="section-box clean-pane animate-fade-up delay-3">
            <h3 class="section-title">自我描述</h3>
            <p class="section-desc">描述你的优势、求职方向或特殊情况，AI 会结合这些信息优化推荐</p>
            <textarea v-model="form.self_description" class="form-textarea" rows="4" placeholder="例如：我是应届计算机本科生，主攻后端开发，对 ML 感兴趣…" maxlength="500"></textarea>
            <p style="text-align:right;font-size:0.75rem;color:var(--c-gray-400);margin-top:4px">{{ form.self_description?.length || 0 }}/500</p>
          </section>

          <!-- ── 错误/成功提示 & 保存 ── -->
          <div v-if="saveMsg" class="msg-bar" :class="saveMsgType" style="margin-bottom:12px">{{ saveMsg }}</div>
          <button type="submit" class="btn btn-primary btn-full" style="font-size:1rem;height:48px" :class="{ 'btn-loading': saveLoading }">
            <span v-if="saveLoading" class="spinner" style="width:16px;height:16px;border-width:1.5px;border-top-color:#fff"></span>
            <span v-else>保存档案</span>
          </button>
        </form>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { profileAPI } from '../api/index'

const router = useRouter()

const pageLoading = ref(true)
const saveLoading = ref(false)
const parseLoading = ref(false)
const resumeText = ref('')
const newSkill = ref('')
const saveMsg = ref('')
const saveMsgType = ref('success')
const parseMsg = ref('')
const parseMsgType = ref('success')
const parseResult = ref(null)

const form = reactive({
  skills: [],
  education: '',
  major: '',
  experience_summary: '',
  experience_years: '',
  expected_salary_min: null,
  expected_salary_max: null,
  preferred_locations: [],
  is_fresh_graduate: false,
  self_description: '',
})

// 地点字符串双向绑定
const locationsStr = computed({
  get: () => form.preferred_locations.join(', '),
  set: (val) => {
    form.preferred_locations = val.split(/[,，]/).map(s => s.trim()).filter(Boolean)
  },
})

onMounted(async () => {
  try {
    const res = await profileAPI.get()
    if (res.success && res.data) {
      // 只复制后端返回的已有字段，避免覆盖默认值
      const d = res.data
      if (d.skills) form.skills = d.skills
      if (d.education) form.education = d.education
      if (d.major) form.major = d.major
      if (d.experience_summary) form.experience_summary = d.experience_summary
      if (d.experience_years) form.experience_years = String(d.experience_years)
      if (d.preferred_locations) form.preferred_locations = d.preferred_locations
      if (d.expected_salary_min != null) form.expected_salary_min = d.expected_salary_min
      if (d.expected_salary_max != null) form.expected_salary_max = d.expected_salary_max
      if (d.is_fresh_graduate != null) form.is_fresh_graduate = d.is_fresh_graduate
      if (d.self_description) form.self_description = d.self_description
    }
  } catch (e) {
    // 档案不存在时正常忽略
  } finally {
    pageLoading.value = false
  }
})

const addSkill = () => {
  const s = newSkill.value.trim()
  if (s && !form.skills.includes(s)) {
    form.skills.push(s)
    newSkill.value = ''
  }
}

const removeSkill = (idx) => form.skills.splice(idx, 1)

const handleParseResume = async () => {
  if (!resumeText.value.trim()) return
  parseLoading.value = true
  parseMsg.value = ''
  parseResult.value = null
  try {
    const res = await profileAPI.uploadResume({ resume_text: resumeText.value })
    if (res.success) {
      parseResult.value = res.data
      parseMsg.value = '解析成功！点击「应用到档案」更新信息'
      parseMsgType.value = 'success'
    } else {
      parseMsg.value = res.message || '解析失败'
      parseMsgType.value = 'error'
    }
  } catch (e) {
    parseMsg.value = e?.message || '解析出错'
    parseMsgType.value = 'error'
  } finally {
    parseLoading.value = false
  }
}

const applyParseResult = () => {
  if (!parseResult.value) return
  const r = parseResult.value
  if (r.skills?.length) form.skills = [...new Set([...form.skills, ...r.skills])]
  if (r.education) form.education = r.education
  if (r.major) form.major = r.major
  if (r.preferred_locations?.length) form.preferred_locations = r.preferred_locations
  parseMsg.value = '✅ 已应用，记得点击保存！'
  parseMsgType.value = 'success'
}

const handleSave = async () => {
  saveLoading.value = true
  saveMsg.value = ''
  try {
    // 过滤掉 null/undefined，避免触发后端 422
    const payload = Object.fromEntries(
      Object.entries({ ...form }).filter(([, v]) => v !== null && v !== undefined && v !== '')
    )
    const res = await profileAPI.update(payload)
    if (res.success) {
      saveMsg.value = '✅ 档案保存成功！'
      saveMsgType.value = 'success'
    } else {
      saveMsg.value = res.message || '保存失败'
      saveMsgType.value = 'error'
    }
  } catch (e) {
    const detail = e?.detail || e?.message || '未知错误'
    saveMsg.value = '保存失败：' + detail
    saveMsgType.value = 'error'
  } finally {
    saveLoading.value = false
    setTimeout(() => { saveMsg.value = '' }, 4000)
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: transparent;
}

.profile-page-title {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

/* 布局 */
.profile-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--space-10);
  padding-top: var(--space-10);
  padding-bottom: var(--space-20);
  align-items: start;
}

@media (max-width: 900px) {
  .profile-layout { grid-template-columns: 1fr; }
}

/* 左侧简历面板 */
.resume-panel {
  position: sticky;
  top: 72px;
}

/* 公共 section 卡片 */
.section-box {
  padding: var(--space-6);
  margin-bottom: var(--space-5);
}

.section-title {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}

.section-desc {
  font-size: 0.8rem;
  color: var(--c-gray-400);
  line-height: 1.5;
  margin-bottom: var(--space-4);
}

/* 解析结果 */
.parse-result {
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--c-gray-50);
  border: var(--border);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.parse-result-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--c-black);
}

.parse-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.parse-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-gray-400);
}

.parse-value {
  font-size: 0.85rem;
  color: var(--c-gray-700);
}

/* 技能标签 */
.skills-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* 添加行 */
.add-row {
  display: flex;
  gap: var(--space-2);
}
.add-row .form-input { flex: 1; }

/* 双栏表单 */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
@media (max-width: 600px) { .form-row { grid-template-columns: 1fr; } }

/* 薪资行 */
.salary-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.salary-sep { color: var(--c-gray-400); flex-shrink: 0; }

/* 复选框 */
.check-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.875rem;
  color: var(--c-gray-700);
  cursor: pointer;
}
.check-input {
  width: 16px;
  height: 16px;
  accent-color: var(--c-black);
  cursor: pointer;
}

/* 右侧表单 */
.profile-form-panel { min-height: 400px; }

/* 加载状态 */
.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: var(--space-16);
}

/* 消息条 */
.msg-bar {
  font-size: 0.85rem;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  line-height: 1.5;
}
.msg-bar.success { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }
.msg-bar.error { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
</style>

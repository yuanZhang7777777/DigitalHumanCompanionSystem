<template>
  <canvas ref="canvasRef" class="particle-bg"></canvas>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  isSpeaking: {
    type: Boolean,
    default: false
  }
})

const canvasRef = ref(null)
let ctx = null
let animationFrameId = null
let particles = []
const P_COUNT = 150 // 粒子数量更多，因为现在是非常细小的划痕短线

// 交互相关
let mouse = { x: -1000, y: -1000, radius: 150 }

// 响应式状态参数设置
let currentSpeedMultiplier = 1
let targetSpeedMultiplier = 1
let currentGlow = 0
let targetGlow = 0

class Particle {
  constructor(w, h) {
    this.w = w
    this.h = h
    this.reset(true)
  }

  reset(initial = false) {
    // 围绕屏幕中心生成，形成一个有纵深的巨型旋涡
    const cx = this.w / 2
    const cy = this.h / 2
    
    // 随机极坐标生成
    this.angle = Math.random() * Math.PI * 2
    // 距离中心的半径
    this.radius = initial ? Math.random() * (this.w * 0.8) : this.w * 0.8
    
    // 轨道角速度 (越靠近中心越快，或加入随机扰动)
    this.angularSpeed = (Math.random() * 0.001 + 0.0005) * (Math.random() < 0.5 ? 1 : -1)

    // Antigravity 的特征：极其细小的各种蓝色的短短划线短横
    this.length = Math.random() * 6 + 2 // dash length 2-8px
    this.thickness = Math.random() * 1.5 + 0.5 // thickness 0.5-2px
    
    // 随机 Google 经典全家桶色系 (以 Blue 为主)
    const colors = [
      { r: 66, g: 133, b: 244 }, // Blue
      { r: 66, g: 133, b: 244 }, // Blue
      { r: 66, g: 133, b: 244 }, // Blue
      { r: 234, g: 67, b: 53 },  // Red
      { r: 251, g: 188, b: 4 },  // Yellow
      { r: 52, g: 168, b: 83 },  // Green
      { r: 161, g: 66, b: 244 }  // Purple
    ]
    
    let chosenColor = colors[Math.floor(Math.random() * colors.length)]

    this.r = chosenColor.r
    this.g = chosenColor.g
    this.b = chosenColor.b
    
    this.baseAlpha = Math.random() * 0.5 + 0.2
    
    // 初始化直角坐标
    this.updateCartesian()
  }

  updateCartesian() {
    this.x = this.w / 2 + Math.cos(this.angle) * this.radius
    this.y = this.h / 2 + Math.sin(this.angle) * this.radius
  }

  update(speedMult) {
    // 持续公转
    this.angle += this.angularSpeed * speedMult
    // 缓慢向中心收缩或扩散
    this.radius += (Math.sin(this.angle * 3) * 0.5)
    
    this.updateCartesian()

    // 物理交互：当鼠标靠近粒子时产生“推斥引力 (Repel)”
    let dx = mouse.x - this.x
    let dy = mouse.y - this.y
    let distance = Math.sqrt(dx * dx + dy * dy)
    
    if (distance < mouse.radius) {
      const forceDirectionX = dx / distance
      const forceDirectionY = dy / distance
      const force = (mouse.radius - distance) / mouse.radius
      const repelSpeed = 20 // 强烈的排斥
      
      this.radius += force * repelSpeed // 将其向外推
      this.updateCartesian()
    }
  }

  draw(ctx, glow) {
    ctx.beginPath()
    // 画短线：短线的方向顺着轨道切线方向
    const tangentAngle = this.angle + Math.PI / 2
    
    const x1 = this.x - Math.cos(tangentAngle) * (this.length / 2)
    const y1 = this.y - Math.sin(tangentAngle) * (this.length / 2)
    const x2 = this.x + Math.cos(tangentAngle) * (this.length / 2)
    const y2 = this.y + Math.sin(tangentAngle) * (this.length / 2)
    
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    
    // 说话时粒子微微发亮并变粗
    const currentAlpha = Math.min(1, this.baseAlpha + glow * 0.5)
    ctx.strokeStyle = `rgba(${this.r}, ${this.g}, ${this.b}, ${currentAlpha})`
    ctx.lineWidth = this.thickness + glow * 1.5
    ctx.lineCap = 'round'
    ctx.stroke()
  }
}

const resizeCanvas = () => {
  if (!canvasRef.value) return
  const w = window.innerWidth
  const h = window.innerHeight
  const dpr = window.devicePixelRatio || 1
  canvasRef.value.width = w * dpr
  canvasRef.value.height = h * dpr
  canvasRef.value.style.width = `${w}px`
  canvasRef.value.style.height = `${h}px`
  ctx.scale(dpr, dpr)
  
  if (particles.length !== P_COUNT) {
    particles = Array.from({ length: P_COUNT }, () => new Particle(w, h))
  } else {
    particles.forEach(p => { p.w = w; p.h = h })
  }
}

const onMouseMove = (e) => {
  mouse.x = e.clientX
  mouse.y = e.clientY
}

const onMouseLeave = () => {
  mouse.x = -1000
  mouse.y = -1000
}

const animate = () => {
  if (!canvasRef.value || !ctx) return
  const w = canvasRef.value.width / (window.devicePixelRatio || 1)
  const h = canvasRef.value.height / (window.devicePixelRatio || 1)

  currentSpeedMultiplier += (targetSpeedMultiplier - currentSpeedMultiplier) * 0.05
  currentGlow += (targetGlow - currentGlow) * 0.08

  const time = Date.now()
  // 完全透明，露出底部的 CSS radial-gradient 边缘发光
  ctx.clearRect(0, 0, w, h)

  particles.forEach(p => {
    p.update(currentSpeedMultiplier)
    p.draw(ctx, currentGlow)
  })
  
  // 白色版本不需要连线，只需要那些细小的彩色 dashes 悬浮即可

  animationFrameId = requestAnimationFrame(animate)
}

watch(() => props.isSpeaking, (newVal) => {
  if (newVal) {
    targetSpeedMultiplier = 4.0 // 说话时全局神经元流转大幅加速
    targetGlow = 0.8          // 闪烁高亮
  } else {
    targetSpeedMultiplier = 1
    targetGlow = 0
  }
})

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseout', onMouseLeave)
  animate()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCanvas)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseout', onMouseLeave)
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
})
</script>

<style scoped>
.particle-bg {
  position: fixed; /* 全局悬浮，无需随滚动条滚动 */
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: -1; /* 垫衬在最底部 */
}
</style>

<template>
  <div class="app-wrapper">
    <!-- 全局统一的高级引力交互背景 (Global Antigravity Background) -->
    <ParticleBackground />

    <!-- 页面内容 -->
    <router-view v-slot="{ Component, route }">
      <transition name="page" mode="out-in">
        <component :is="Component" :key="route.path" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import ParticleBackground from './components/ParticleBackground.vue'
</script>

<style>
.app-wrapper {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 页面切换动画 (Antigravity-style slow fade) */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}

.page-enter-from {
  opacity: 0;
  transform: scale(0.98);
}

.page-leave-to {
  opacity: 0;
}
</style>
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'

const { t } = useI18n()
</script>

<template>
  <MainLayout>
    <div class="autolikes-page">
      <h1 class="page-title">{{ t('nav.autoLikes') }}</h1>

      <div class="coming-soon-card">
        <div class="icon-wrapper">
          <i class="pi pi-heart"></i>
        </div>
        <h2 class="title">{{ t('nav.autoLikes') }}</h2>
        <p class="description">{{ t('comingSoon') }}</p>
        <div class="decoration">
          <div class="circle circle-1"></div>
          <div class="circle circle-2"></div>
          <div class="circle circle-3"></div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.autolikes-page {
  max-width: 800px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  margin-bottom: 28px;
  letter-spacing: -0.5px;
}

.coming-soon-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 20px;
  padding: 60px 40px;
  text-align: center;
  position: relative;
  overflow: hidden;
}

.icon-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.2) 0%, rgba(219, 39, 119, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
}

.icon-wrapper i {
  font-size: 36px;
  color: #ec4899;
}

.title {
  font-size: 24px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
}

.description {
  font-size: 16px;
  color: #6b7280;
}

.decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.1) 0%, rgba(219, 39, 119, 0.05) 100%);
}

.circle-1 {
  width: 200px;
  height: 200px;
  top: -100px;
  right: -50px;
}

.circle-2 {
  width: 150px;
  height: 150px;
  bottom: -75px;
  left: -50px;
}

.circle-3 {
  width: 100px;
  height: 100px;
  top: 50%;
  right: 20%;
  opacity: 0.5;
}
</style>

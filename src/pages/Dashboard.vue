<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue'
</script>

<template>
  <MainLayout>
    <div class="dashboard">
      <h1 class="text-2xl font-semibold mb-6">Dashboard</h1>

      <!-- Stats cards -->
      <div class="grid grid-cols-4 gap-4 mb-8">
        <div class="card-dashed p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="icon-wrapper">
              <i class="pi pi-users"></i>
            </div>
            <span class="text-gray-400 text-sm">Accounts</span>
          </div>
          <div class="text-3xl font-bold">0</div>
          <div class="text-xs text-gray-500 mt-1">0 active</div>
        </div>

        <div class="card-dashed p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="icon-wrapper" style="background: linear-gradient(135deg, #3b82f6, #2563eb);">
              <i class="pi pi-globe"></i>
            </div>
            <span class="text-gray-400 text-sm">Proxies</span>
          </div>
          <div class="text-3xl font-bold">0</div>
          <div class="text-xs text-gray-500 mt-1">0 working</div>
        </div>

        <div class="card-dashed p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="icon-wrapper" style="background: linear-gradient(135deg, #10b981, #059669);">
              <i class="pi pi-heart"></i>
            </div>
            <span class="text-gray-400 text-sm">Likes Today</span>
          </div>
          <div class="text-3xl font-bold">0</div>
          <div class="text-xs text-gray-500 mt-1">0 tasks</div>
        </div>

        <div class="card-dashed p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="icon-wrapper" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
              <i class="pi pi-comments"></i>
            </div>
            <span class="text-gray-400 text-sm">Comments Today</span>
          </div>
          <div class="text-3xl font-bold">0</div>
          <div class="text-xs text-gray-500 mt-1">0 tasks</div>
        </div>
      </div>

      <!-- Quick actions -->
      <div class="card-dashed">
        <div class="section-header">
          <div class="icon-wrapper">
            <i class="pi pi-bolt"></i>
          </div>
          <h2 class="font-medium">Quick Actions</h2>
        </div>
        <div class="p-5 grid grid-cols-3 gap-4">
          <router-link to="/accounts" class="action-card">
            <i class="pi pi-plus text-xl mb-2"></i>
            <span>Add Account</span>
          </router-link>
          <router-link to="/proxy" class="action-card">
            <i class="pi pi-globe text-xl mb-2"></i>
            <span>Add Proxy</span>
          </router-link>
          <router-link to="/autolikes" class="action-card">
            <i class="pi pi-heart text-xl mb-2"></i>
            <span>New Like Task</span>
          </router-link>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  border: 2px dashed rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  color: #888;
  text-decoration: none;
  transition: all 0.2s;
}

.action-card:hover {
  border-color: rgba(168, 85, 247, 0.5);
  border-style: solid;
  color: #a855f7;
  background: rgba(168, 85, 247, 0.05);
}
</style>

<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
</script>

<template>
  <MainLayout>
    <div class="settings-page">
      <h1 class="text-2xl font-semibold mb-6">Settings</h1>

      <div class="card-dashed">
        <div class="section-header">
          <div class="icon-wrapper">
            <i class="pi pi-cog"></i>
          </div>
          <h2 class="font-medium">Application</h2>
        </div>
        <div class="p-5">
          <div class="flex items-center justify-between py-3 border-b border-gray-800">
            <div>
              <div class="font-medium">Data Location</div>
              <div class="text-sm text-gray-500">~/Nexus</div>
            </div>
            <Button label="Change" severity="secondary" size="small" />
          </div>

          <div class="flex items-center justify-between py-3 border-b border-gray-800">
            <div>
              <div class="font-medium">Clear All Data</div>
              <div class="text-sm text-gray-500">Remove all accounts, proxies and tasks</div>
            </div>
            <Button label="Clear" severity="danger" size="small" />
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

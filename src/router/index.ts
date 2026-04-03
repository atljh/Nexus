import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/pages/Dashboard.vue')
    },
    {
      path: '/accounts',
      name: 'accounts',
      component: () => import('@/pages/Accounts.vue')
    },
    {
      path: '/proxy',
      name: 'proxy',
      component: () => import('@/pages/Proxy.vue')
    },
    {
      path: '/autolikes',
      name: 'autolikes',
      component: () => import('@/pages/AutoLikes.vue')
    },
    {
      path: '/autocomments',
      name: 'autocomments',
      component: () => import('@/pages/AutoComments.vue')
    },
    {
      path: '/warming',
      name: 'warming',
      component: () => import('@/pages/AccountWarming.vue')
    },
    {
      path: '/channels',
      name: 'channels',
      component: () => import('@/pages/ChannelRegistry.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/pages/Settings.vue')
    },
    {
      path: '/task/:id',
      name: 'taskResults',
      component: () => import('@/pages/TaskResults.vue')
    }
  ]
})

export default router

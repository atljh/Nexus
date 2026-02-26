import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Task,
  TaskLog,
  CreateLikesTaskParams,
  CreateCommentsTaskParams,
  TaskStats,
  TaskStatus,
  CommentTemplate,
  TargetChannel
} from '@/types'

interface TasksResponse {
  data?: Task[]
  length?: number
  [index: number]: Task
}

interface TaskResponse extends Task {}

interface TaskLogsResponse {
  data?: TaskLog[]
  length?: number
  [index: number]: TaskLog
}

export const useTaskStore = defineStore('task', () => {
  // State
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const taskLogs = ref<TaskLog[]>([])
  const stats = ref<TaskStats>({
    total: 0,
    running: 0,
    pending: 0,
    completed: 0,
    failed: 0
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pollingInterval = ref<number | null>(null)

  // Getters
  const activeTasks = computed(() =>
    tasks.value.filter(t => t.status === 'running' || t.status === 'pending')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  const hasRunningTasks = computed(() =>
    tasks.value.some(t => t.status === 'running')
  )

  // Actions
  async function fetchTasks(taskType?: string, status?: TaskStatus) {
    loading.value = true
    error.value = null
    try {
      let endpoint = '/api/tasks'
      const params: string[] = []
      if (taskType) params.push(`task_type=${taskType}`)
      if (status) params.push(`status=${status}`)
      if (params.length) endpoint += '?' + params.join('&')

      const response = await window.api.get(endpoint) as TasksResponse
      tasks.value = Array.isArray(response) ? response : (response.data || [])
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch tasks'
      console.error('Failed to fetch tasks:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchActiveTasks() {
    try {
      const response = await window.api.get('/api/tasks/active') as TasksResponse
      const active = Array.isArray(response) ? response : (response.data || [])
      // Update only active tasks in the list
      for (const activeTask of active) {
        const index = tasks.value.findIndex(t => t.id === activeTask.id)
        if (index >= 0) {
          tasks.value[index] = activeTask
        } else {
          tasks.value.unshift(activeTask)
        }
      }
    } catch (e) {
      console.error('Failed to fetch active tasks:', e)
    }
  }

  async function fetchTask(taskId: number) {
    try {
      const response = await window.api.get(`/api/tasks/${taskId}`) as TaskResponse
      currentTask.value = response
      // Update in list too
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index >= 0) {
        tasks.value[index] = response
      }
      return response
    } catch (e) {
      console.error('Failed to fetch task:', e)
      return null
    }
  }

  async function fetchTaskLogs(taskId: number, successFilter?: boolean) {
    try {
      let endpoint = `/api/tasks/${taskId}/logs`
      if (successFilter !== undefined) {
        endpoint += `?success=${successFilter}`
      }
      const response = await window.api.get(endpoint) as TaskLogsResponse
      taskLogs.value = Array.isArray(response) ? response : (response.data || [])
    } catch (e) {
      console.error('Failed to fetch task logs:', e)
    }
  }

  async function fetchStats() {
    try {
      const response = await window.api.get('/api/tasks/stats/summary') as TaskStats
      stats.value = response
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
  }

  async function createLikesTask(params: CreateLikesTaskParams): Promise<Task | null> {
    loading.value = true
    error.value = null
    try {
      const response = await window.api.post('/api/tasks/likes', params) as TaskResponse
      tasks.value.unshift(response)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create task'
      console.error('Failed to create task:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function createCommentsTask(params: CreateCommentsTaskParams): Promise<Task | null> {
    loading.value = true
    error.value = null
    try {
      const response = await window.api.post('/api/tasks/comments', params) as TaskResponse
      tasks.value.unshift(response)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create comments task'
      console.error('Failed to create comments task:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  // Comment Templates
  const templates = ref<CommentTemplate[]>([])

  async function fetchTemplates() {
    try {
      const response = await window.api.get('/api/tasks/templates') as CommentTemplate[]
      templates.value = Array.isArray(response) ? response : []
    } catch (e) {
      console.error('Failed to fetch templates:', e)
    }
  }

  async function createTemplate(name: string, content: string, isDefault = false): Promise<CommentTemplate | null> {
    try {
      const response = await window.api.post('/api/tasks/templates', {
        name,
        content,
        is_default: isDefault
      }) as CommentTemplate
      templates.value.push(response)
      return response
    } catch (e) {
      console.error('Failed to create template:', e)
      return null
    }
  }

  async function deleteTemplate(templateId: number): Promise<boolean> {
    try {
      await window.api.delete(`/api/tasks/templates/${templateId}`)
      templates.value = templates.value.filter(t => t.id !== templateId)
      return true
    } catch (e) {
      console.error('Failed to delete template:', e)
      return false
    }
  }

  // Target Channels
  const targetChannels = ref<TargetChannel[]>([])

  async function fetchTargetChannels(taskId: number) {
    try {
      const response = await window.api.get(`/api/tasks/${taskId}/channels`) as TargetChannel[]
      targetChannels.value = Array.isArray(response) ? response : []
    } catch (e) {
      console.error('Failed to fetch target channels:', e)
    }
  }

  async function startTask(taskId: number): Promise<boolean> {
    try {
      const response = await window.api.post(`/api/tasks/${taskId}/start`, {}) as TaskResponse
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index >= 0) {
        tasks.value[index] = response
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = response
      }
      // Start polling for updates
      startPolling()
      return true
    } catch (e) {
      console.error('Failed to start task:', e)
      return false
    }
  }

  async function pauseTask(taskId: number): Promise<boolean> {
    try {
      const response = await window.api.post(`/api/tasks/${taskId}/pause`, {}) as TaskResponse
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index >= 0) {
        tasks.value[index] = response
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = response
      }
      return true
    } catch (e) {
      console.error('Failed to pause task:', e)
      return false
    }
  }

  async function cancelTask(taskId: number): Promise<boolean> {
    try {
      const response = await window.api.post(`/api/tasks/${taskId}/cancel`, {}) as TaskResponse
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index >= 0) {
        tasks.value[index] = response
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = response
      }
      return true
    } catch (e) {
      console.error('Failed to cancel task:', e)
      return false
    }
  }

  async function deleteTask(taskId: number): Promise<boolean> {
    try {
      await window.api.delete(`/api/tasks/${taskId}`)
      tasks.value = tasks.value.filter(t => t.id !== taskId)
      if (currentTask.value?.id === taskId) {
        currentTask.value = null
      }
      return true
    } catch (e) {
      console.error('Failed to delete task:', e)
      return false
    }
  }

  // Polling for real-time updates
  function startPolling(intervalMs = 2000) {
    if (pollingInterval.value) return
    pollingInterval.value = window.setInterval(async () => {
      if (hasRunningTasks.value) {
        await fetchActiveTasks()
        if (currentTask.value && currentTask.value.status === 'running') {
          await fetchTask(currentTask.value.id)
          await fetchTaskLogs(currentTask.value.id)
        }
      } else {
        stopPolling()
      }
    }, intervalMs)
  }

  function stopPolling() {
    if (pollingInterval.value) {
      window.clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  function $reset() {
    stopPolling()
  }

  function setCurrentTask(task: Task | null) {
    currentTask.value = task
    if (task) {
      fetchTaskLogs(task.id)
    } else {
      taskLogs.value = []
    }
  }

  return {
    // State
    tasks,
    currentTask,
    taskLogs,
    stats,
    loading,
    error,
    templates,
    targetChannels,

    // Getters
    activeTasks,
    completedTasks,
    hasRunningTasks,

    // Actions
    fetchTasks,
    fetchActiveTasks,
    fetchTask,
    fetchTaskLogs,
    fetchStats,
    createLikesTask,
    createCommentsTask,
    startTask,
    pauseTask,
    cancelTask,
    deleteTask,
    startPolling,
    stopPolling,
    $reset,
    setCurrentTask,
    // Templates
    fetchTemplates,
    createTemplate,
    deleteTemplate,
    // Target Channels
    fetchTargetChannels
  }
})

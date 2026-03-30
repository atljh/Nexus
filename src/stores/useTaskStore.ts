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
  ImportCommentTemplatesResult,
  TargetChannel
} from '@/types'

interface TasksResponse {
  data?: Task[]
  length?: number
  [index: number]: Task
}

type TaskResponse = Task

interface TaskLogsResponse {
  data?: TaskLog[]
  length?: number
  [index: number]: TaskLog
}

async function fileToUpload(name: string, file: File): Promise<UploadFile> {
  const buffer = await file.arrayBuffer()
  return {
    name,
    data: new Uint8Array(buffer),
    filename: file.name
  }
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
  const currentTaskType = ref<string | null>(null)
  let isPollingTickRunning = false

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
  let _tasksFetchedAt = 0
  let _tasksFetchedKey = ''
  const CACHE_TTL = 5000

  async function fetchTasks(taskType?: string, status?: TaskStatus, force = false) {
    const cacheKey = `${taskType || ''}_${status || ''}`
    if (!force && tasks.value.length > 0 && cacheKey === _tasksFetchedKey && Date.now() - _tasksFetchedAt < CACHE_TTL) {
      return
    }
    loading.value = true
    error.value = null
    currentTaskType.value = taskType || null
    try {
      let endpoint = '/api/tasks'
      const params: string[] = []
      if (taskType) params.push(`task_type=${taskType}`)
      if (status) params.push(`status=${status}`)
      if (params.length) endpoint += '?' + params.join('&')

      const response = await window.api.get(endpoint) as TasksResponse
      tasks.value = Array.isArray(response) ? response : (response.data || [])
      _tasksFetchedAt = Date.now()
      _tasksFetchedKey = cacheKey
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
      const allActive = Array.isArray(response) ? response : (response.data || [])
      // Filter by current task type to avoid cross-type pollution
      const active = currentTaskType.value
        ? allActive.filter(t => t.task_type === currentTaskType.value)
        : allActive
      const activeIds = new Set(active.map(t => t.id))

      // Update active tasks in the list
      for (const activeTask of active) {
        const index = tasks.value.findIndex(t => t.id === activeTask.id)
        if (index >= 0) {
          tasks.value[index] = activeTask
        } else {
          tasks.value.unshift(activeTask)
        }
      }

      // Detect tasks that were running but disappeared from active list
      // (they completed, failed, or were cancelled on the backend)
      const vanished = tasks.value.filter(
        t => (t.status === 'running' || t.status === 'pending') && !activeIds.has(t.id)
      )
      const currentTaskId = currentTask.value?.id ?? null
      await Promise.all(vanished.map(async task => {
        const shouldSyncCurrentTask = task.id === currentTaskId
        await fetchTask(task.id, { setCurrent: shouldSyncCurrentTask })
        if (shouldSyncCurrentTask) {
          await fetchTaskLogs(task.id)
        }
      }))
    } catch (e) {
      console.error('Failed to fetch active tasks:', e)
    }
  }

  async function fetchTask(taskId: number, options: { setCurrent?: boolean } = {}) {
    const { setCurrent = true } = options
    try {
      const response = await window.api.get(`/api/tasks/${taskId}`) as TaskResponse
      if (setCurrent) {
        currentTask.value = response
      }
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

  const logsHasMore = ref(false)
  const LOGS_PAGE_SIZE = 100

  async function fetchTaskLogs(taskId: number, successFilter?: boolean, append = false) {
    try {
      const offset = append ? taskLogs.value.length : 0
      let endpoint = `/api/tasks/${taskId}/logs?limit=${LOGS_PAGE_SIZE}&offset=${offset}`
      if (successFilter !== undefined) {
        endpoint += `&success=${successFilter}`
      }
      const response = await window.api.get(endpoint) as TaskLogsResponse
      const logs = Array.isArray(response) ? response : (response.data || [])
      if (append) {
        taskLogs.value = [...taskLogs.value, ...logs]
      } else {
        taskLogs.value = logs
      }
      logsHasMore.value = logs.length >= LOGS_PAGE_SIZE
    } catch (e) {
      console.error('Failed to fetch task logs:', e)
    }
  }

  async function fetchAllTaskLogs(taskId: number): Promise<void> {
    try {
      const response = await window.api.get(`/api/tasks/${taskId}/logs?limit=1000&offset=0`) as TaskLogsResponse
      const logs = Array.isArray(response) ? response : (response.data || [])
      taskLogs.value = logs
      logsHasMore.value = false
    } catch (e) {
      console.error('Failed to fetch all task logs:', e)
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

  let _templatesFetchedAt = 0

  async function fetchTemplates(force = false) {
    if (!force && templates.value.length > 0 && Date.now() - _templatesFetchedAt < CACHE_TTL) {
      return
    }
    try {
      const response = await window.api.get('/api/tasks/templates') as CommentTemplate[]
      templates.value = Array.isArray(response) ? response : []
      _templatesFetchedAt = Date.now()
    } catch (e) {
      console.error('Failed to fetch templates:', e)
    }
  }

  async function createTemplate(
    name: string,
    content: string,
    category = 'General',
    isDefault = false
  ): Promise<CommentTemplate | null> {
    try {
      const response = await window.api.post('/api/tasks/templates', {
        name,
        content,
        category,
        is_default: isDefault
      }) as CommentTemplate
      templates.value.push(response)
      return response
    } catch (e) {
      console.error('Failed to create template:', e)
      return null
    }
  }

  async function updateTemplate(
    templateId: number,
    payload: { name: string; content: string; category?: string; is_default?: boolean }
  ): Promise<CommentTemplate | null> {
    try {
      const response = await window.api.put(`/api/tasks/templates/${templateId}`, {
        name: payload.name,
        content: payload.content,
        category: payload.category || 'General',
        is_default: payload.is_default ?? false
      }) as CommentTemplate
      const index = templates.value.findIndex(t => t.id === templateId)
      if (index >= 0) {
        templates.value[index] = response
      }
      return response
    } catch (e) {
      console.error('Failed to update template:', e)
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

  async function importTemplates(file: File, category?: string): Promise<ImportCommentTemplatesResult | null> {
    try {
      const upload = await fileToUpload('file', file)
      const fields: Record<string, string> = category?.trim()
        ? { category: category.trim() }
        : {}
      const response = await window.api.upload('/api/tasks/templates/import', [upload], fields) as ImportCommentTemplatesResult
      await fetchTemplates(true)
      return response
    } catch (e) {
      console.error('Failed to import templates:', e)
      return null
    }
  }

  // Per-account stats
  interface AccountStat {
    account_id: number
    phone: string | null
    username: string | null
    first_name: string | null
    status: string | null
    success: number
    failed: number
    total: number
  }
  const accountStats = ref<AccountStat[]>([])

  async function fetchAccountStats(taskId: number) {
    try {
      const response = await window.api.get(`/api/tasks/${taskId}/account-stats`) as AccountStat[]
      accountStats.value = Array.isArray(response) ? response : []
    } catch (e) {
      console.error('Failed to fetch account stats:', e)
    }
  }

  // Duplicate task
  async function duplicateTask(taskId: number): Promise<Task | null> {
    try {
      const response = await window.api.post(`/api/tasks/duplicate/${taskId}`, {}) as TaskResponse
      tasks.value.unshift(response)
      return response
    } catch (e) {
      console.error('Failed to duplicate task:', e)
      return null
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
    error.value = null
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
    error.value = null
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
    error.value = null
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
    error.value = null
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

  async function restartTask(taskId: number): Promise<Task | null> {
    error.value = null
    try {
      const response = await window.api.post(`/api/tasks/${taskId}/restart`, {}) as TaskResponse
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index >= 0) {
        tasks.value[index] = response
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = response
      }
      return response
    } catch (e) {
      console.error('Failed to restart task:', e)
      return null
    }
  }

  // Polling for real-time updates
  async function runPollingTick() {
    if (isPollingTickRunning) return
    isPollingTickRunning = true

    try {
      if (hasRunningTasks.value) {
        await fetchActiveTasks()
        if (currentTask.value) {
          if (currentTask.value.status === 'running') {
            await fetchTask(currentTask.value.id)
            await fetchTaskLogs(currentTask.value.id)
          } else if (['completed', 'failed', 'cancelled'].includes(currentTask.value.status)) {
            await fetchTaskLogs(currentTask.value.id)
          }
        }
      } else {
        if (currentTask.value) {
          await fetchTaskLogs(currentTask.value.id)
        }
        stopPolling()
      }
    } finally {
      isPollingTickRunning = false
    }
  }

  function startPolling(intervalMs = 2000) {
    if (pollingInterval.value) return
    void runPollingTick()
    pollingInterval.value = window.setInterval(() => {
      void runPollingTick()
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
    isPollingTickRunning = false
    error.value = null
    loading.value = false
    taskLogs.value = []
    accountStats.value = []
    targetChannels.value = []
    currentTask.value = null
    currentTaskType.value = null
  }

  function setCurrentTask(task: Task | null) {
    currentTask.value = task
    if (task) {
      fetchTaskLogs(task.id)
    } else {
      taskLogs.value = []
      accountStats.value = []
      targetChannels.value = []
    }
  }

  return {
    // State
    tasks,
    currentTask,
    taskLogs,
    logsHasMore,
    accountStats,
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
    fetchAllTaskLogs,
    fetchStats,
    createLikesTask,
    createCommentsTask,
    startTask,
    pauseTask,
    cancelTask,
    deleteTask,
    restartTask,
    startPolling,
    stopPolling,
    $reset,
    setCurrentTask,
    // Templates
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    importTemplates,
    // Account stats
    fetchAccountStats,
    duplicateTask,
    // Target Channels
    fetchTargetChannels
  }
})

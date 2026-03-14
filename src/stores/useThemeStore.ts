import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

let lightThemeLoaded = false

async function loadLightThemeCSS() {
  if (lightThemeLoaded) return
  await import('@/assets/light-theme.css')
  lightThemeLoaded = true
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>('dark')
  const resolvedTheme = ref<'light' | 'dark'>('dark')

  // Initialize theme from localStorage
  const savedTheme = localStorage.getItem('nexus-theme') as Theme | null
  if (savedTheme && ['light', 'dark', 'system'].includes(savedTheme)) {
    theme.value = savedTheme
  }

  // Watch system preference
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

  function updateResolvedTheme() {
    if (theme.value === 'system') {
      resolvedTheme.value = mediaQuery.matches ? 'dark' : 'light'
    } else {
      resolvedTheme.value = theme.value
    }
    applyTheme()
  }

  function applyTheme() {
    // Apply to both html and body for maximum compatibility
    const html = document.documentElement
    const body = document.body

    if (resolvedTheme.value === 'dark') {
      html.classList.add('dark')
      html.classList.remove('light')
      body?.classList.add('dark')
      body?.classList.remove('light')
    } else {
      // Lazy-load light theme CSS on first use
      loadLightThemeCSS()
      html.classList.add('light')
      html.classList.remove('dark')
      body?.classList.add('light')
      body?.classList.remove('dark')
    }
  }

  function setTheme(newTheme: Theme) {
    theme.value = newTheme
    localStorage.setItem('nexus-theme', newTheme)
    updateResolvedTheme()
  }

  function toggleTheme() {
    if (theme.value === 'dark') {
      setTheme('light')
    } else if (theme.value === 'light') {
      setTheme('dark')
    } else {
      // If system, toggle to opposite of current resolved
      setTheme(resolvedTheme.value === 'dark' ? 'light' : 'dark')
    }
  }

  // Listen for system theme changes
  mediaQuery.addEventListener('change', () => {
    if (theme.value === 'system') {
      updateResolvedTheme()
    }
  })

  // Initialize on load
  updateResolvedTheme()

  return {
    theme,
    resolvedTheme,
    setTheme,
    toggleTheme
  }
})

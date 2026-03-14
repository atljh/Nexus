import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // Treat webview as native Electron element
          isCustomElement: (tag) => tag === 'webview'
        }
      }
    }),
    electron([
      {
        entry: 'electron/main.ts',
        onstart(args) {
          args.startup()
        },
        vite: {
          build: {
            outDir: 'dist-electron/main',
            rollupOptions: {
              external: ['electron']
            }
          }
        }
      },
      {
        entry: 'electron/preload.ts',
        onstart(args) {
          args.reload()
        },
        vite: {
          build: {
            outDir: 'dist-electron/preload'
          }
        }
      },
      {
        entry: 'electron/webview-preload.ts',
        onstart(args) {
          args.reload()
        },
        vite: {
          build: {
            outDir: 'dist-electron/preload'
          }
        }
      }
    ]),
    renderer()
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'primevue': ['primevue/config', '@primevue/themes/aura', 'primevue/toastservice', 'primevue/confirmationservice'],
          'vendor': ['vue', 'vue-router', 'pinia', 'vue-i18n']
        }
      }
    }
  }
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  },
  build: {
    outDir: '../backend/web',
    emptyOutDir: true,
    // 相对路径：放在子目录或本地 file:// 下都能取到资源
    base: './',
    rollupOptions: {
      output: { inlineDynamicImports: true }
    }
  }
})

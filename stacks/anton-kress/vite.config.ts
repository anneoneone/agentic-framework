import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@canvas': resolve(__dirname, 'src/canvas'),
      '@sections': resolve(__dirname, 'src/sections'),
      '@hooks': resolve(__dirname, 'src/hooks'),
      '@store': resolve(__dirname, 'src/store'),
      '@lib': resolve(__dirname, 'src/lib'),
      '@animations': resolve(__dirname, 'src/animations'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Three.js ecosystem — large, lazy-loaded via React.lazy(SceneRoot)
          three: ['three', '@react-three/fiber', '@react-three/drei'],
          // Animation libs — loaded after initial paint
          gsap: ['gsap'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})

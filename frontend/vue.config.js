const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true
      },
      // HexStrike API 代理（只代理 API 路径，避免与前端路由 /hexstrike 冲突）
      // 注意：/hexstrike 路径是前端路由，不应该被代理
      // 只有 /hexstrike/health、/hexstrike/api 等 API 路径才需要代理
      '/hexstrike/health': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        ws: true,
        pathRewrite: {
          '^/hexstrike': ''
        }
      },
      '/hexstrike/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        ws: true,
        pathRewrite: {
          '^/hexstrike': ''
        }
      }
    }
  },
  outputDir: process.env.VUE_CLI_BUILD_OUTPUT_DIR || '../project/frontend',
  // 独立前端部署（Nginx 根路径）用 VUE_APP_PUBLIC_PATH=/；Django 合署用 /static/frontend/
  publicPath: process.env.VUE_APP_PUBLIC_PATH || (process.env.NODE_ENV === 'production' ? '/static/frontend/' : '/')
})





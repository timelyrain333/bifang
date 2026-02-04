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
      }
    }
  },
  outputDir: process.env.VUE_CLI_BUILD_OUTPUT_DIR || '../project/frontend',
  // 独立前端部署（Nginx 根路径）用 VUE_APP_PUBLIC_PATH=/；Django 合署用 /static/frontend/
  publicPath: process.env.VUE_APP_PUBLIC_PATH || (process.env.NODE_ENV === 'production' ? '/static/frontend/' : '/')
})





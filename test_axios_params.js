const axios = require('axios');

// 测试Axios如何处理数组参数
const params = {
  page: 1,
  page_size: 20,
  asset_type: ['account', 'port']
};

// 模拟Axios的URL构建
const url = new URL('http://localhost:8000/api/assets/');
Object.keys(params).forEach(key => {
  const value = params[key];
  if (Array.isArray(value)) {
    value.forEach(v => {
      url.searchParams.append(key, v);
    });
  } else {
    url.searchParams.append(key, value);
  }
});

console.log('URL:', url.toString());
console.log('Query string:', url.search);

<template>
  <div class="system-config">
    <!-- 阿里云配置卡片 -->
    <el-card class="config-section-card">
      <template #header>
        <div class="card-header">
          <span>阿里云配置</span>
          <el-button type="primary" :icon="Plus" @click="handleAddAliyun">新增配置</el-button>
        </div>
      </template>
      
      <!-- 阿里云配置列表 -->
      <el-table :data="aliyunConfigs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="api_endpoint" label="API地址" width="250" show-overflow-tooltip />
        <el-table-column prop="region_id" label="地域" width="120" />
        <el-table-column prop="access_key_id" label="AccessKey ID" width="200" show-overflow-tooltip />
        <el-table-column prop="is_default" label="默认配置" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning">是</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row, 'aliyun')">编辑</el-button>
            <el-button type="success" link size="small" @click="handleSetDefault(row)" v-if="!row.is_default">设为默认</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- AWS配置卡片 -->
    <el-card class="config-section-card">
      <template #header>
        <div class="card-header">
          <span>AWS配置</span>
          <el-button type="primary" :icon="Plus" @click="handleAddAWS">新增配置</el-button>
        </div>
      </template>
      
      <!-- AWS配置列表 -->
      <el-table :data="awsConfigs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="region" label="区域" width="150" />
        <el-table-column prop="access_key_id" label="Access Key ID" width="200" show-overflow-tooltip />
        <el-table-column prop="is_default" label="默认配置" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning">是</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row, 'aws')">编辑</el-button>
            <el-button type="success" link size="small" @click="handleSetDefault(row, 'aws')" v-if="!row.is_default">设为默认</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row, 'aws')">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 通义千问AI配置卡片 -->
    <el-card class="config-section-card">
      <template #header>
        <div class="card-header">
          <span>通义千问AI配置</span>
          <el-button type="primary" :icon="Plus" @click="handleAddQianwen">新增配置</el-button>
        </div>
      </template>
      
      <!-- 通义千问配置列表 -->
      <el-table :data="qianwenConfigs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="qianwen_api_base" label="API地址" width="300" show-overflow-tooltip />
        <el-table-column prop="qianwen_model" label="模型名称" width="150" />
        <el-table-column prop="qianwen_enabled" label="启用状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.qianwen_enabled" type="success">已启用</el-tag>
            <el-tag v-else type="info">未启用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row, 'qianwen')">编辑</el-button>
            <el-button type="warning" link size="small" @click="handleTestQianwen(row)" v-if="row.has_qianwen_api_key">测试连接</el-button>
            <el-button type="success" link size="small" @click="handleTestAiParsing(row)" v-if="row.has_qianwen_api_key && row.qianwen_enabled">测试解析</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 钉钉配置卡片 -->
    <el-card class="config-section-card">
      <template #header>
        <div class="card-header">
          <span>钉钉配置</span>
          <el-button type="primary" :icon="Plus" @click="handleAddDingtalk">新增配置</el-button>
        </div>
      </template>
      
      <!-- 钉钉配置列表 -->
      <el-table :data="dingtalkConfigs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="dingtalk_webhook" label="钉钉Webhook" width="300" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.dingtalk_webhook">{{ row.dingtalk_webhook.substring(0, 50) }}...</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dingtalk_enabled" label="启用状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.dingtalk_enabled" type="success">已启用</el-tag>
            <el-tag v-else type="info">未启用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row, 'dingtalk')">编辑</el-button>
            <el-button type="warning" link size="small" @click="handleTestDingtalk(row)" :disabled="!row.dingtalk_webhook">测试钉钉</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 飞书配置卡片 -->
    <el-card class="config-section-card">
      <template #header>
        <div class="card-header">
          <span>飞书配置</span>
          <el-button type="primary" :icon="Plus" @click="handleAddFeishu">新增配置</el-button>
        </div>
      </template>
      
      <!-- 飞书配置列表 -->
      <el-table :data="feishuConfigs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="feishu_webhook" label="飞书Webhook" width="300" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.feishu_webhook">{{ row.feishu_webhook.substring(0, 50) }}...</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="feishu_use_long_connection" label="长连接" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.feishu_use_long_connection" type="success">已启用</el-tag>
            <el-tag v-else type="info">未启用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="feishu_enabled" label="启用状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.feishu_enabled" type="success">已启用</el-tag>
            <el-tag v-else type="info">未启用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row, 'feishu')">编辑</el-button>
            <el-button type="warning" link size="small" @click="handleTestFeishu(row)" :disabled="!row.feishu_webhook">测试飞书</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 配置表单对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="140px"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入配置名称" style="width: 100%" />
          <div class="form-help">用于区分不同的配置，如：生产环境、测试环境</div>
        </el-form-item>
        
        <!-- 阿里云配置字段 -->
        <template v-if="currentConfigType === 'aliyun' || currentConfigType === 'both'">
          <el-divider content-position="left">阿里云配置</el-divider>
          <el-form-item label="API地址" prop="api_endpoint">
            <el-input v-model="formData.api_endpoint" placeholder="例如: https://sas.cn-hangzhou.aliyuncs.com" style="width: 100%" />
          </el-form-item>
          <el-form-item label="AccessKey ID" prop="access_key_id">
            <el-input v-model="formData.access_key_id" placeholder="请输入AccessKey ID" style="width: 100%" />
          </el-form-item>
          <el-form-item label="AccessKey Secret" prop="access_key_secret">
            <el-input
              v-model="formData.access_key_secret"
              type="password"
              placeholder="请输入AccessKey Secret"
              show-password
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="地域ID" prop="region_id">
            <el-select v-model="formData.region_id" placeholder="请选择地域" style="width: 100%">
              <el-option label="华东1（杭州）" value="cn-hangzhou" />
              <el-option label="华东2（上海）" value="cn-shanghai" />
              <el-option label="华北1（青岛）" value="cn-qingdao" />
              <el-option label="华北2（北京）" value="cn-beijing" />
              <el-option label="华北3（张家口）" value="cn-zhangjiakou" />
              <el-option label="华北5（呼和浩特）" value="cn-hohhot" />
              <el-option label="华南1（深圳）" value="cn-shenzhen" />
              <el-option label="西南1（成都）" value="cn-chengdu" />
              <el-option label="中国（香港）" value="cn-hongkong" />
            </el-select>
          </el-form-item>
        </template>
        
        <!-- 通义千问AI配置字段 -->
        <template v-if="currentConfigType === 'qianwen' || currentConfigType === 'both'">
          <el-divider content-position="left">通义千问AI配置</el-divider>
          <el-form-item label="API Key" prop="qianwen_api_key">
            <el-input
              v-model="formData.qianwen_api_key"
              type="password"
              placeholder="请输入阿里云百炼平台的API Key"
              show-password
              style="width: 100%"
            />
            <div class="form-help">在阿里云百炼控制台获取API Key</div>
          </el-form-item>
          <el-form-item label="API地址" prop="qianwen_api_base">
            <el-input
              v-model="formData.qianwen_api_base"
              placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
              style="width: 100%"
            />
            <div class="form-help">中国大陆使用默认地址，国际区域使用：https://dashscope-intl.aliyuncs.com/compatible-mode/v1</div>
          </el-form-item>
          <el-form-item label="模型名称" prop="qianwen_model">
            <el-select v-model="formData.qianwen_model" placeholder="请选择模型" style="width: 100%">
              <el-option label="qwen-plus（推荐）" value="qwen-plus" />
              <el-option label="qwen-max" value="qwen-max" />
              <el-option label="qwen-turbo" value="qwen-turbo" />
            </el-select>
            <div class="form-help">用于解析漏洞详情的AI模型</div>
          </el-form-item>
          <el-form-item label="启用AI解析" prop="qianwen_enabled">
            <el-switch v-model="formData.qianwen_enabled" />
            <div class="form-help">启用后，漏洞采集插件将使用AI模型解析漏洞详情，提高解析准确性</div>
          </el-form-item>
        </template>
        
        <!-- 钉钉配置字段 -->
        <template v-if="currentConfigType === 'dingtalk' || currentConfigType === 'both'">
          <el-divider content-position="left">钉钉配置</el-divider>
          <el-form-item label="钉钉Webhook" prop="dingtalk_webhook">
            <el-input
              v-model="formData.dingtalk_webhook"
              type="textarea"
              :rows="2"
              placeholder="请输入钉钉机器人Webhook地址，例如：https://oapi.dingtalk.com/robot/send?access_token=xxx"
            />
          </el-form-item>
          <el-form-item label="钉钉签名密钥" prop="dingtalk_secret">
            <el-input
              v-model="formData.dingtalk_secret"
              type="password"
              placeholder="如使用加签方式，请输入签名密钥（可选）"
              show-password
              style="width: 100%"
            />
          </el-form-item>
          <el-divider content-position="left">应用凭证（用于智能体交互）</el-divider>
          <el-form-item label="钉钉App ID" prop="dingtalk_app_id">
            <el-input
              v-model="formData.dingtalk_app_id"
              placeholder="请输入钉钉机器人应用的App ID"
            />
            <div class="form-help">在钉钉开放平台创建应用后获取</div>
          </el-form-item>
          <el-form-item label="钉钉Client ID" prop="dingtalk_client_id">
            <el-input
              v-model="formData.dingtalk_client_id"
              placeholder="请输入钉钉机器人应用的Client ID"
            />
            <div class="form-help">在钉钉开放平台创建应用后获取</div>
          </el-form-item>
          <el-form-item label="钉钉Client Secret" prop="dingtalk_client_secret">
            <el-input
              v-model="formData.dingtalk_client_secret"
              type="password"
              placeholder="请输入钉钉机器人应用的Client Secret"
              show-password
              style="width: 100%"
            />
            <div class="form-help">在钉钉开放平台创建应用后获取</div>
          </el-form-item>
          <el-form-item label="使用流式推送" prop="dingtalk_use_stream_push">
            <el-switch v-model="formData.dingtalk_use_stream_push" />
            <div class="form-help">使用流式推送方式接收事件，无需公网地址（推荐）</div>
          </el-form-item>
          <el-form-item label="启用钉钉通知" prop="dingtalk_enabled">
            <el-switch v-model="formData.dingtalk_enabled" />
          </el-form-item>
        </template>
        
        <!-- 飞书配置字段 -->
        <template v-if="currentConfigType === 'feishu' || currentConfigType === 'both'">
          <el-divider content-position="left">飞书配置</el-divider>
          <el-form-item label="使用长连接" prop="feishu_use_long_connection">
            <el-switch v-model="formData.feishu_use_long_connection" />
            <div class="form-help">使用长连接方式接收事件，无需公网地址（推荐）</div>
          </el-form-item>
          <template v-if="formData.feishu_use_long_connection">
            <el-form-item label="飞书App ID" prop="feishu_app_id">
              <el-input
                v-model="formData.feishu_app_id"
                placeholder="请输入飞书机器人应用的App ID"
              />
              <div class="form-help">在飞书开放平台创建应用后获取</div>
            </el-form-item>
            <el-form-item label="飞书App Secret" prop="feishu_app_secret">
              <el-input
                v-model="formData.feishu_app_secret"
                type="password"
                placeholder="请输入飞书机器人应用的App Secret"
                show-password
                style="width: 100%"
              />
            </el-form-item>
          </template>
          <el-form-item label="飞书Webhook" prop="feishu_webhook">
            <el-input
              v-model="formData.feishu_webhook"
              type="textarea"
              :rows="2"
              placeholder="请输入飞书机器人Webhook地址（可选），例如：https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
            />
            <div class="form-help">
              <div v-if="formData.feishu_use_long_connection">
                <strong>企业自建应用：</strong>不需要配置Webhook，系统会通过SDK API发送消息
              </div>
              <div v-else>
                <strong>自定义机器人：</strong>需要配置Webhook地址，用于发送消息到飞书群
              </div>
            </div>
          </el-form-item>
          <el-form-item label="飞书签名密钥" prop="feishu_secret">
            <el-input
              v-model="formData.feishu_secret"
              type="password"
              placeholder="如使用加签方式，请输入签名密钥（可选）"
              show-password
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="启用飞书通知" prop="feishu_enabled">
            <el-switch v-model="formData.feishu_enabled" />
          </el-form-item>
          <el-form-item label="关联AI配置" prop="qianwen_config" v-if="formData.feishu_use_long_connection">
            <el-select 
              v-model="formData.qianwen_config" 
              placeholder="请选择已存在的通义千问AI配置（用于智能体功能）" 
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="aiConfig in availableAiConfigs"
                :key="aiConfig.id"
                :label="`${aiConfig.name}${aiConfig.qianwen_enabled ? ' (已启用)' : ' (未启用)'}`"
                :value="aiConfig.id"
                :disabled="!aiConfig.qianwen_enabled || !aiConfig.has_qianwen_api_key"
              >
                <span>{{ aiConfig.name }}</span>
                <el-tag v-if="aiConfig.qianwen_enabled" type="success" size="small" style="margin-left: 8px">已启用</el-tag>
                <el-tag v-else type="info" size="small" style="margin-left: 8px">未启用</el-tag>
              </el-option>
            </el-select>
            <div class="form-help">选择已存在的通义千问AI配置，用于飞书智能体功能。如果未选择，智能体功能将不可用。</div>
          </el-form-item>
        </template>
        
        <!-- 其他配置 -->
        <el-form-item label="是否默认配置" prop="is_default" v-if="currentConfigType === 'aliyun'">
          <el-switch v-model="formData.is_default" />
          <div class="form-help">设置为默认配置后，创建任务时将自动使用此配置</div>
        </el-form-item>
        
        <el-form-item label="是否启用" prop="is_active">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
        
        <el-form-item label="配置描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入配置描述（可选）"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ElLoading } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '../api'

export default {
  name: 'SystemConfig',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const submitting = ref(false)
    const testingConfig = ref(false)
    const configs = ref([])
    const awsConfigs = ref([])
    const dialogVisible = ref(false)
    const formRef = ref(null)
    const isEdit = ref(false)
    const currentId = ref(null)
    const currentConfigType = ref('aliyun') // 'aliyun', 'dingtalk', 'feishu', 'qianwen', 'both', 'aws'
    
    const formData = reactive({
      name: '',
      config_type: 'aliyun',
      api_endpoint: 'https://sas.cn-hangzhou.aliyuncs.com',
      access_key_id: '',
      access_key_secret: '',
      region_id: 'cn-hangzhou',
      qianwen_api_key: '',
      qianwen_api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      qianwen_model: 'qwen-plus',
      qianwen_enabled: false,
      dingtalk_webhook: '',
      dingtalk_secret: '',
      dingtalk_app_id: '',
      dingtalk_client_id: '',
      dingtalk_client_secret: '',
      dingtalk_use_stream_push: false,
      dingtalk_enabled: false,
      feishu_webhook: '',
      feishu_secret: '',
      feishu_app_id: '',
      feishu_app_secret: '',
      feishu_use_long_connection: false,
      feishu_enabled: false,
      qianwen_config: null, // 关联的AI配置ID
      is_default: false,
      is_active: true,
      description: ''
    })
    
    // 计算属性：分离不同类型的配置
    const aliyunConfigs = computed(() => {
      return configs.value.filter(config => 
        config.config_type === 'aliyun' || config.config_type === 'both'
      )
    })
    
    const qianwenConfigs = computed(() => {
      return configs.value.filter(config => 
        config.config_type === 'qianwen' || config.config_type === 'both'
      )
    })
    
    // 可用的AI配置（用于飞书配置选择，只显示已启用且有API Key的配置）
    const availableAiConfigs = computed(() => {
      return qianwenConfigs.value.filter(config => 
        config.is_active && config.qianwen_enabled && config.has_qianwen_api_key
      )
    })
    
    const dingtalkConfigs = computed(() => {
      return configs.value.filter(config => 
        config.config_type === 'dingtalk' || config.config_type === 'both'
      )
    })
    
    const feishuConfigs = computed(() => {
      return configs.value.filter(config => 
        config.config_type === 'feishu' || config.config_type === 'both'
      )
    })
    
    const dialogTitle = computed(() => {
      const typeMap = {
        'aliyun': '阿里云',
        'dingtalk': '钉钉',
        'feishu': '飞书',
        'qianwen': '通义千问AI',
        'both': '系统'
      }
      const typeText = typeMap[currentConfigType.value] || '系统'
      return isEdit.value ? `编辑${typeText}配置` : `新增${typeText}配置`
    })
    
    const canTestConfig = computed(() => {
      if (currentConfigType.value === 'dingtalk') {
        return !!formData.dingtalk_webhook
      } else if (currentConfigType.value === 'feishu') {
        return !!formData.feishu_webhook
      }
      return false
    })
    
    const formRules = {
      name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }]
    }
    
    const loadConfigs = async () => {
      loading.value = true
      try {
        const [aliyunResponse, awsResponse] = await Promise.all([
          api.get('/aliyun-configs/'),
          api.get('/aws-configs/')
        ])
        configs.value = aliyunResponse.results || (Array.isArray(aliyunResponse) ? aliyunResponse : [])
        awsConfigs.value = awsResponse.results || (Array.isArray(awsResponse) ? awsResponse : [])
      } catch (error) {
        console.error('加载配置失败:', error)
        ElMessage.error('加载配置失败')
      } finally {
        loading.value = false
      }
    }
    
    const handleAddAliyun = () => {
      isEdit.value = false
      currentId.value = null
      currentConfigType.value = 'aliyun'
      resetForm('aliyun')
      dialogVisible.value = true
    }
    
    const handleAddQianwen = () => {
      isEdit.value = false
      currentId.value = null
      currentConfigType.value = 'qianwen'
      resetForm('qianwen')
      dialogVisible.value = true
    }
    
    const handleAddDingtalk = () => {
      isEdit.value = false
      currentId.value = null
      currentConfigType.value = 'dingtalk'
      resetForm('dingtalk')
      dialogVisible.value = true
    }
    
    const handleAddFeishu = () => {
      isEdit.value = false
      currentId.value = null
      currentConfigType.value = 'feishu'
      resetForm('feishu')
      dialogVisible.value = true
    }
    
    const handleAddAWS = () => {
      // 跳转到AWS配置页面
      router.push('/aws-config')
    }
    
    const handleEdit = (row, type) => {
      if (type === 'aws') {
        // AWS配置跳转到专门的AWS配置页面
        router.push(`/aws-config`)
        return
      }
      isEdit.value = true
      currentId.value = row.id
      currentConfigType.value = type || row.config_type || 'aliyun'
      
      Object.assign(formData, {
        name: row.name || '',
        config_type: row.config_type || currentConfigType.value,
        api_endpoint: row.api_endpoint || 'https://sas.cn-hangzhou.aliyuncs.com',
        access_key_id: row.access_key_id || '',
        access_key_secret: '', // 不显示已加密的Secret
        region_id: row.region_id || 'cn-hangzhou',
        qianwen_api_key: '', // 不显示已加密的API Key
        qianwen_api_base: row.qianwen_api_base || 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        qianwen_model: row.qianwen_model || 'qwen-plus',
        qianwen_enabled: row.qianwen_enabled || false,
        dingtalk_webhook: row.dingtalk_webhook || '',
        dingtalk_secret: '', // 不显示已加密的Secret
        dingtalk_app_id: row.dingtalk_app_id || '',
        dingtalk_client_id: row.dingtalk_client_id || '',
        dingtalk_client_secret: '', // 不显示已加密的Secret
        dingtalk_use_stream_push: row.dingtalk_use_stream_push || false,
        dingtalk_enabled: row.dingtalk_enabled || false,
        feishu_webhook: row.feishu_webhook || '',
        feishu_secret: '', // 不显示已加密的Secret
        feishu_app_id: row.feishu_app_id || '',
        feishu_app_secret: '', // 不显示已加密的Secret
        feishu_use_long_connection: row.feishu_use_long_connection || false,
        feishu_enabled: row.feishu_enabled || false,
        qianwen_config: row.qianwen_config || null, // 关联的AI配置ID
        is_default: row.is_default || false,
        is_active: row.is_active !== undefined ? row.is_active : true,
        description: row.description || ''
      })
      dialogVisible.value = true
    }
    
    const resetForm = (type) => {
      const baseData = {
        name: '',
        config_type: type || 'aliyun',
        is_active: true,
        description: ''
      }
      
      if (type === 'aliyun') {
        Object.assign(formData, {
          ...baseData,
          api_endpoint: 'https://sas.cn-hangzhou.aliyuncs.com',
          access_key_id: '',
          access_key_secret: '',
          region_id: 'cn-hangzhou',
          is_default: false,
          dingtalk_webhook: '',
          dingtalk_secret: '',
          dingtalk_app_id: '',
          dingtalk_client_id: '',
          dingtalk_client_secret: '',
          dingtalk_enabled: false
        })
      } else if (type === 'qianwen') {
        Object.assign(formData, {
          ...baseData,
          qianwen_api_key: '',
          qianwen_api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
          qianwen_model: 'qwen-plus',
          qianwen_enabled: false,
          is_default: false
        })
      } else if (type === 'dingtalk') {
        Object.assign(formData, {
          ...baseData,
          dingtalk_webhook: '',
          dingtalk_secret: '',
          dingtalk_app_id: '',
          dingtalk_client_id: '',
          dingtalk_client_secret: '',
          dingtalk_use_stream_push: false,
          dingtalk_enabled: false,
          api_endpoint: '',
          access_key_id: '',
          access_key_secret: '',
          region_id: '',
          is_default: false
        })
      } else if (type === 'feishu') {
        Object.assign(formData, {
          ...baseData,
          feishu_webhook: '',
          feishu_secret: '',
          feishu_app_id: '',
          feishu_app_secret: '',
          feishu_use_long_connection: false,
          feishu_enabled: false,
          qianwen_config: null,
          api_endpoint: '',
          access_key_id: '',
          access_key_secret: '',
          region_id: '',
          is_default: false
        })
      }
      
      if (formRef.value) {
        formRef.value.resetFields()
      }
    }
    
    const handleSubmit = async () => {
      if (!formRef.value) return
      
      await formRef.value.validate(async (valid) => {
        if (!valid) return
        
        submitting.value = true
        try {
          const data = { ...formData }
          data.config_type = currentConfigType.value
          
          // 如果编辑时Secret为空，则不发送（保持原值）
          if (isEdit.value && !data.access_key_secret) {
            delete data.access_key_secret
          }
          if (isEdit.value && !data.dingtalk_secret) {
            delete data.dingtalk_secret
          }
          // 如果编辑时Secret为空，则不发送（保持原值）
          if (isEdit.value && !data.dingtalk_client_secret) {
            delete data.dingtalk_client_secret
          }
          if (isEdit.value && !data.feishu_secret) {
            delete data.feishu_secret
          }
          if (isEdit.value && !data.feishu_app_secret) {
            delete data.feishu_app_secret
          }
          if (isEdit.value && !data.qianwen_api_key) {
            delete data.qianwen_api_key
          }
          
          if (isEdit.value) {
            await api.put(`/aliyun-configs/${currentId.value}/`, data)
            ElMessage.success('配置更新成功')
          } else {
            await api.post('/aliyun-configs/', data)
            ElMessage.success('配置创建成功')
          }
          
          dialogVisible.value = false
          loadConfigs()
        } catch (error) {
          console.error('保存配置失败:', error)
          // 处理字段级别的验证错误
          if (error.response?.data) {
            const errorData = error.response.data
            if (errorData.name) {
              ElMessage.error(Array.isArray(errorData.name) ? errorData.name[0] : errorData.name)
            } else if (errorData.error) {
              ElMessage.error(errorData.error)
            } else if (errorData.non_field_errors) {
              ElMessage.error(Array.isArray(errorData.non_field_errors) ? errorData.non_field_errors[0] : errorData.non_field_errors)
            } else {
              ElMessage.error('保存配置失败')
            }
          } else {
            ElMessage.error('保存配置失败')
          }
        } finally {
          submitting.value = false
        }
      })
    }
    
    const handleSetDefault = async (row, type) => {
      try {
        if (type === 'aws') {
          // AWS配置通过更新接口设置默认
          await api.put(`/aws-configs/${row.id}/`, { ...row, is_default: true })
        } else {
          await api.post(`/aliyun-configs/${row.id}/set_default/`)
        }
        ElMessage.success('已设置为默认配置')
        loadConfigs()
      } catch (error) {
        console.error('设置默认配置失败:', error)
        ElMessage.error('设置默认配置失败')
      }
    }
    
    const handleTestQianwen = async (row) => {
      try {
        const response = await api.post(`/aliyun-configs/${row.id}/test_qianwen/`)
        // 注意：api.post() 已经通过响应拦截器返回了 response.data
        ElMessage.success(response.message || '测试连接成功')
      } catch (error) {
        console.error('测试通义千问配置失败:', error)
        ElMessage.error(error.response?.data?.error || '测试失败')
      }
    }
    
    const handleTestAiParsing = async (row) => {
      let loadingInstance = null
      try {
        loadingInstance = ElLoading.service({
          lock: true,
          text: '正在测试AI解析功能，请稍候...',
          background: 'rgba(0, 0, 0, 0.7)'
        })
        
        const response = await api.post(`/aliyun-configs/${row.id}/test_ai_parsing/`)
        
        if (loadingInstance) {
          loadingInstance.close()
          loadingInstance = null
        }
        
        // 注意：api.post() 已经通过响应拦截器返回了 response.data
        // 所以 response 直接就是后端返回的JSON对象 {message: "...", data: {...}}
        const result = response.data || {}
        
        // 调试日志
        console.log('AI解析响应:', response)
        console.log('解析结果:', result)
        
        // 检查result是否是空对象或无效
        if (!result || (typeof result === 'object' && Object.keys(result).length === 0)) {
          ElMessage.warning('AI解析返回了空结果，可能是API配置有误或模型返回格式异常')
          return
        }
        
        // 格式化显示解析结果
        const resultLines = []
        resultLines.push('=== AI解析测试成功 ===\n')
        if (result.basic_description) resultLines.push(`基本描述: ${result.basic_description.substring(0, 200)}`)
        if (result.vulnerability_description) resultLines.push(`\n漏洞描述: ${result.vulnerability_description.substring(0, 300)}`)
        if (result.impact) resultLines.push(`\n影响: ${result.impact.substring(0, 200)}`)
        if (result.severity) resultLines.push(`\n严重程度: ${result.severity}`)
        if (result.affected_component) resultLines.push(`\n受影响组件: ${result.affected_component}`)
        if (result.affected_versions) resultLines.push(`\n受影响版本: ${result.affected_versions}`)
        if (result.solution) resultLines.push(`\n解决方案: ${result.solution.substring(0, 200)}`)
        if (result.mitigation) resultLines.push(`\n缓解措施: ${result.mitigation.substring(0, 200)}`)
        
        const resultText = resultLines.join('\n')
        
        ElMessageBox.alert(
          resultText,
          'AI解析测试结果',
          {
            confirmButtonText: '确定',
            type: 'success',
            dangerouslyUseHTMLString: false
          }
        )
      } catch (error) {
        // 确保加载状态关闭
        if (loadingInstance) {
          loadingInstance.close()
          loadingInstance = null
        }
        
        console.error('测试AI解析失败:', error)
        const errorMsg = error.response?.data?.error || error.response?.data?.message || error.message || '测试失败'
        const detail = error.response?.data?.detail || ''
        if (detail) {
          ElMessage.error(`${errorMsg}\n${detail}`)
        } else {
          ElMessage.error(errorMsg)
        }
      }
    }
    
    const handleTestDingtalk = async (row) => {
      try {
        const response = await api.post(`/aliyun-configs/${row.id}/test_dingtalk/`)
        // 注意：api.post() 已经通过响应拦截器返回了 response.data
        ElMessage.success(response.message || '测试消息发送成功')
      } catch (error) {
        console.error('测试钉钉配置失败:', error)
        ElMessage.error(error.response?.data?.error || '测试失败')
      }
    }
    
    const handleTestFeishu = async (row) => {
      try {
        const response = await api.post(`/aliyun-configs/${row.id}/test_feishu/`)
        ElMessage.success(response.message || '测试消息发送成功')
      } catch (error) {
        console.error('测试飞书配置失败:', error)
        ElMessage.error(error.response?.data?.error || '测试失败')
      }
    }
    
    const handleTestConfigInDialog = async () => {
      if (currentConfigType.value === 'dingtalk') {
        if (!formData.dingtalk_webhook) {
          ElMessage.warning('请先填写钉钉Webhook地址')
          return
        }
        testingConfig.value = true
        try {
          const response = await api.post('/aliyun-configs/test_dingtalk_config/', {
            dingtalk_webhook: formData.dingtalk_webhook,
            dingtalk_secret: formData.dingtalk_secret || ''
          })
          ElMessage.success(response.message || '测试消息发送成功')
        } catch (error) {
          console.error('测试钉钉配置失败:', error)
          ElMessage.error(error.response?.data?.error || '测试失败')
        } finally {
          testingConfig.value = false
        }
      } else if (currentConfigType.value === 'feishu') {
        if (!formData.feishu_webhook) {
          ElMessage.warning('请先填写飞书Webhook地址')
          return
        }
        testingConfig.value = true
        try {
          const response = await api.post('/aliyun-configs/test_feishu_config/', {
            feishu_webhook: formData.feishu_webhook,
            feishu_secret: formData.feishu_secret || ''
          })
          ElMessage.success(response.message || '测试消息发送成功')
        } catch (error) {
          console.error('测试飞书配置失败:', error)
          ElMessage.error(error.response?.data?.error || '测试失败')
        } finally {
          testingConfig.value = false
        }
      }
    }
    
    const handleDelete = async (row, type) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除配置"${row.name}"吗？`,
          '确认删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        if (type === 'aws') {
          await api.delete(`/aws-configs/${row.id}/`)
        } else {
          await api.delete(`/aliyun-configs/${row.id}/`)
        }
        ElMessage.success('删除成功')
        loadConfigs()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除配置失败:', error)
          ElMessage.error('删除配置失败')
        }
      }
    }
    
    onMounted(() => {
      loadConfigs()
    })
    
    return {
      loading,
      submitting,
      testingConfig,
      canTestConfig,
      configs,
      aliyunConfigs,
      awsConfigs,
      dingtalkConfigs,
      feishuConfigs,
      dialogVisible,
      formRef,
      formData,
      formRules,
      dialogTitle,
      currentConfigType,
      Plus,
      handleAddAliyun,
      handleAddAWS,
      handleAddQianwen,
      handleAddDingtalk,
      handleAddFeishu,
      handleEdit,
      handleSubmit,
      handleSetDefault,
      handleTestQianwen,
      handleTestAiParsing,
      handleTestDingtalk,
      handleTestFeishu,
      handleTestConfigInDialog,
      handleDelete,
      qianwenConfigs,
      availableAiConfigs
    }
  }
}
</script>

<style scoped>
.system-config {
  padding: 20px;
}

.config-section-card {
  margin-bottom: 20px;
}

.config-section-card:last-child {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
  font-size: 16px;
}

.form-help {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>

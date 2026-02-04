<template>
  <div class="task-form">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑任务' : '新建任务' }}</span>
        </div>
      </template>
      
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入任务名称" />
        </el-form-item>
        
        <el-form-item label="关联插件" prop="plugin">
          <el-select v-model="form.plugin" placeholder="请选择插件" @change="handlePluginChange">
            <el-option
              v-for="plugin in plugins"
              :key="plugin.id"
              :label="`${plugin.name} (${getPluginTypeName(plugin.plugin_type)})`"
              :value="plugin.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="阿里云配置" v-if="selectedPluginType !== 'aws'">
          <el-select v-model="form.aliyun_config" placeholder="请选择阿里云配置（可选，为空则使用默认配置）" clearable>
            <el-option
              v-for="config in aliyunConfigs"
              :key="config.id"
              :label="`${config.name}${config.is_default ? ' (默认)' : ''}`"
              :value="config.id"
            />
          </el-select>
          <div class="form-help">选择要使用的阿里云配置，如果不选择则自动使用默认配置</div>
        </el-form-item>
        
        <el-form-item label="AWS配置" v-if="selectedPluginType === 'aws'">
          <el-select v-model="form.aws_config" placeholder="请选择AWS配置（可选，为空则使用默认配置）" clearable>
            <el-option
              v-for="config in awsConfigs"
              :key="config.id"
              :label="`${config.name}${config.is_default ? ' (默认)' : ''}`"
              :value="config.id"
            />
          </el-select>
          <div class="form-help">选择要使用的AWS配置，如果不选择则自动使用默认配置</div>
        </el-form-item>
        
        <el-form-item label="触发类型" prop="trigger_type">
          <el-radio-group v-model="form.trigger_type">
            <el-radio value="manual">手动执行</el-radio>
            <el-radio value="cron">定时执行</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item
          v-if="form.trigger_type === 'cron'"
          label="Cron表达式"
          prop="cron_expression"
        >
          <el-input v-model="form.cron_expression" placeholder="例如: 0 0 * * * (每天0点执行)" />
          <div class="form-help">
            Cron表达式格式: 分 时 日 月 周
            <br />
            示例: 0 0 * * * (每天0点), 0 */6 * * * (每6小时)
          </div>
        </el-form-item>
        
        <el-form-item label="任务配置" prop="config">
          <el-input
            v-model="configJson"
            type="textarea"
            :rows="10"
            placeholder='请输入JSON格式的配置。注意：如果已选择云配置，则无需在此填写认证信息，系统会自动从选择的配置中获取。例如: {"asset_types": ["server", "account"], "page_size": 100}'
          />
          <div class="form-help">
            提示：如果已选择云配置（阿里云或AWS），则无需填写认证信息，只需填写插件特定的配置参数即可
          </div>
        </el-form-item>
        
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSubmit">保存</el-button>
          <el-button @click="handleCancel">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { taskApi } from '../api/task'
import { pluginApi } from '../api/plugin'
import { aliyunConfigApi } from '../api/aliyunConfig'
import { awsConfigApi } from '../api/awsConfig'

export default {
  name: 'TaskForm',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const formRef = ref(null)
    const plugins = ref([])
    const aliyunConfigs = ref([])
    const awsConfigs = ref([])
    const isEdit = computed(() => !!route.params.id)
    
    const selectedPluginType = computed(() => {
      if (!form.plugin) return ''
      const plugin = plugins.value.find(p => p.id === form.plugin)
      return plugin ? (plugin.name.includes('aws') || plugin.name.includes('AWS') ? 'aws' : 'aliyun') : ''
    })
    
    const form = reactive({
      name: '',
      plugin: null,
      aliyun_config: null,
      aws_config: null,
      trigger_type: 'manual',
      cron_expression: '',
      config: {},
      is_active: true
    })
    
    const configJson = computed({
      get: () => JSON.stringify(form.config, null, 2),
      set: (value) => {
        try {
          form.config = JSON.parse(value)
        } catch (e) {
          // 无效JSON时保持原值
        }
      }
    })
    
    const rules = {
      name: [
        { required: true, message: '请输入任务名称', trigger: 'blur' }
      ],
      plugin: [
        { required: true, message: '请选择插件', trigger: 'change' }
      ],
      cron_expression: [
        { required: true, message: '请输入Cron表达式', trigger: 'blur' }
      ]
    }
    
    const loadPlugins = async () => {
      try {
        const response = await pluginApi.getPlugins()
        // 处理分页响应格式：{count, next, previous, results: [...]}
        let pluginList = response.results || response || []
        // 确保是数组并过滤掉无效值
        if (!Array.isArray(pluginList)) {
          pluginList = []
        }
        plugins.value = pluginList.filter(p => p && p.id)
      } catch (error) {
        console.error('加载插件列表失败:', error)
        ElMessage.error('加载插件列表失败')
        plugins.value = []
      }
    }
    
    const loadAliyunConfigs = async () => {
      try {
        const response = await aliyunConfigApi.getConfigs()
        aliyunConfigs.value = response.results || response || []
      } catch (error) {
        console.error('加载阿里云配置列表失败:', error)
        aliyunConfigs.value = []
      }
    }
    
    const loadAWSConfigs = async () => {
      try {
        const response = await awsConfigApi.getConfigs()
        awsConfigs.value = response.results || response || []
      } catch (error) {
        console.error('加载AWS配置列表失败:', error)
        awsConfigs.value = []
      }
    }
    
    const loadTask = async () => {
      if (!isEdit.value) return
      
      try {
        const task = await taskApi.getTask(route.params.id)
        Object.assign(form, {
          name: task.name,
          plugin: task.plugin,
          aliyun_config: task.aliyun_config || null,
          aws_config: task.aws_config || null,
          trigger_type: task.trigger_type,
          cron_expression: task.cron_expression || '',
          config: task.config || {},
          is_active: task.is_active
        })
      } catch (error) {
        ElMessage.error('加载任务详情失败')
        router.push('/tasks')
      }
    }
    
    const handlePluginChange = () => {
      // 插件变更时可以重置配置或加载默认配置
    }
    
    const handleSubmit = async () => {
      try {
        await formRef.value.validate()
        
        // 验证JSON配置
        try {
          JSON.parse(configJson.value)
        } catch (e) {
          ElMessage.error('配置JSON格式错误')
          return
        }
        
        const data = {
          ...form,
          aliyun_config: form.aliyun_config || null,
          aws_config: form.aws_config || null,
          cron_expression: form.trigger_type === 'cron' ? form.cron_expression : ''
        }
        
        if (isEdit.value) {
          await taskApi.updateTask(route.params.id, data)
          ElMessage.success('更新成功')
        } else {
          await taskApi.createTask(data)
          ElMessage.success('创建成功')
        }
        
        router.push('/tasks')
      } catch (error) {
        if (error !== false) { // 验证失败时error为false
          ElMessage.error('保存失败')
        }
      }
    }
    
    const handleCancel = () => {
      router.push('/tasks')
    }
    
    const getPluginTypeName = (type) => {
      const map = {
        'data': '数据记录',
        'collect': '数据采集',
        'risk': '风险检测',
        'dump': '数据导出',
        'alarm': '告警'
      }
      return map[type] || type
    }
    
    onMounted(async () => {
      await loadPlugins()
      await loadAliyunConfigs()
      await loadAWSConfigs()
      await loadTask()
    })
    
    return {
      formRef,
      form,
      configJson,
      plugins,
      aliyunConfigs,
      awsConfigs,
      selectedPluginType,
      isEdit,
      rules,
      handlePluginChange,
      handleSubmit,
      handleCancel,
      getPluginTypeName
    }
  }
}
</script>

<style scoped>
.task-form {
  max-width: 800px;
}

.form-help {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>

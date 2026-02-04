<template>
  <div class="aws-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>AWS配置管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建配置
          </el-button>
        </div>
      </template>
      
      <el-table :data="configs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="region" label="区域" width="150" />
        <el-table-column prop="access_key_id" label="Access Key ID" width="200" show-overflow-tooltip />
        <el-table-column prop="is_default" label="默认配置" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_default ? 'success' : 'info'">
              {{ row.is_default ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button 
              size="small" 
              type="success" 
              @click="handleSetDefault(row)"
              :disabled="row.is_default"
            >
              设为默认
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 配置表单对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑配置' : '新建配置'"
      width="600px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="140px"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入配置名称" />
          <div class="form-help">用于区分不同的配置，如：生产环境、测试环境</div>
        </el-form-item>
        
        <el-form-item label="Access Key ID" prop="access_key_id">
          <el-input v-model="form.access_key_id" placeholder="请输入AWS Access Key ID" />
        </el-form-item>
        
        <el-form-item label="Secret Access Key" prop="secret_access_key">
          <el-input
            v-model="form.secret_access_key"
            type="password"
            placeholder="请输入AWS Secret Access Key"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="区域" prop="region">
          <el-select v-model="form.region" placeholder="请选择AWS区域" style="width: 100%">
            <el-option label="亚太地区（东京）" value="ap-northeast-1" />
            <el-option label="亚太地区（首尔）" value="ap-northeast-2" />
            <el-option label="亚太地区（大阪）" value="ap-northeast-3" />
            <el-option label="亚太地区（新加坡）" value="ap-southeast-1" />
            <el-option label="亚太地区（悉尼）" value="ap-southeast-2" />
            <el-option label="亚太地区（孟买）" value="ap-south-1" />
            <el-option label="美国东部（弗吉尼亚北部）" value="us-east-1" />
            <el-option label="美国东部（俄亥俄）" value="us-east-2" />
            <el-option label="美国西部（加利福尼亚北部）" value="us-west-1" />
            <el-option label="美国西部（俄勒冈）" value="us-west-2" />
            <el-option label="欧洲（爱尔兰）" value="eu-west-1" />
            <el-option label="欧洲（伦敦）" value="eu-west-2" />
            <el-option label="欧洲（法兰克福）" value="eu-central-1" />
            <el-option label="中国（北京）" value="cn-north-1" />
            <el-option label="中国（宁夏）" value="cn-northwest-1" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Session Token" prop="session_token">
          <el-input
            v-model="form.session_token"
            type="password"
            placeholder="临时凭证的Session Token（可选）"
            show-password
          />
          <div class="form-help">仅在使用临时凭证时需要填写</div>
        </el-form-item>
        
        <el-form-item label="是否默认">
          <el-switch v-model="form.is_default" />
          <div class="form-help">设置为默认配置后，创建任务时将自动使用此配置</div>
        </el-form-item>
        
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        
        <el-form-item label="配置描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入配置描述（可选）"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { awsConfigApi } from '../api/awsConfig'

export default {
  name: 'AWSConfig',
  components: {
    Plus
  },
  setup() {
    const loading = ref(false)
    const saving = ref(false)
    const configs = ref([])
    const dialogVisible = ref(false)
    const isEdit = ref(false)
    const formRef = ref(null)
    
    const form = reactive({
      name: '',
      access_key_id: '',
      secret_access_key: '',
      region: 'ap-northeast-1',
      session_token: '',
      is_default: false,
      is_active: true,
      description: ''
    })
    
    const rules = {
      name: [
        { required: true, message: '请输入配置名称', trigger: 'blur' }
      ],
      access_key_id: [
        { required: true, message: '请输入Access Key ID', trigger: 'blur' }
      ],
      secret_access_key: [
        { required: true, message: '请输入Secret Access Key', trigger: 'blur' }
      ],
      region: [
        { required: true, message: '请选择区域', trigger: 'change' }
      ]
    }
    
    const loadConfigs = async () => {
      loading.value = true
      try {
        const response = await awsConfigApi.getConfigs()
        configs.value = response.results || response || []
      } catch (error) {
        ElMessage.error('加载配置列表失败')
        configs.value = []
      } finally {
        loading.value = false
      }
    }
    
    const handleCreate = () => {
      isEdit.value = false
      resetForm()
      dialogVisible.value = true
    }
    
    const handleEdit = (row) => {
      isEdit.value = true
      Object.assign(form, {
        ...row,
        secret_access_key: '',  // 不显示原有Secret
        session_token: ''  // 不显示原有Token
      })
      dialogVisible.value = true
    }
    
    const handleSubmit = async () => {
      if (!formRef.value) return
      
      try {
        await formRef.value.validate()
        saving.value = true
        
        const data = { ...form }
        // 如果编辑时未修改Secret，则不发送该字段
        if (isEdit.value && !data.secret_access_key) {
          delete data.secret_access_key
        }
        // 如果编辑时未修改Token，则不发送该字段
        if (isEdit.value && !data.session_token) {
          delete data.session_token
        }
        
        if (isEdit.value) {
          await awsConfigApi.updateConfig(form.id, data)
          ElMessage.success('更新成功')
        } else {
          await awsConfigApi.createConfig(data)
          ElMessage.success('创建成功')
        }
        
        dialogVisible.value = false
        loadConfigs()
      } catch (error) {
        if (error !== false) {
          ElMessage.error('保存失败')
        }
      } finally {
        saving.value = false
      }
    }
    
    const handleDelete = async (row) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除配置"${row.name}"吗？`,
          '提示',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        await awsConfigApi.deleteConfig(row.id)
        ElMessage.success('删除成功')
        loadConfigs()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }
    
    const handleSetDefault = async (row) => {
      try {
        // 由于后端可能没有set_default接口，我们通过更新is_default字段来实现
        await awsConfigApi.updateConfig(row.id, { ...row, is_default: true })
        ElMessage.success('已设置为默认配置')
        loadConfigs()
      } catch (error) {
        ElMessage.error('设置失败')
      }
    }
    
    const resetForm = () => {
      if (formRef.value) {
        formRef.value.resetFields()
      }
      Object.assign(form, {
        name: '',
        access_key_id: '',
        secret_access_key: '',
        region: 'ap-northeast-1',
        session_token: '',
        is_default: false,
        is_active: true,
        description: ''
      })
      delete form.id
    }
    
    onMounted(() => {
      loadConfigs()
    })
    
    return {
      loading,
      saving,
      configs,
      dialogVisible,
      isEdit,
      formRef,
      form,
      rules,
      handleCreate,
      handleEdit,
      handleSubmit,
      handleDelete,
      handleSetDefault,
      resetForm
    }
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-help {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>

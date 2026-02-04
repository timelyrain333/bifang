<template>
  <div class="aliyun-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>阿里云配置管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建配置
          </el-button>
        </div>
      </template>
      
      <el-table :data="configs" v-loading="loading" stripe>
        <el-table-column prop="name" label="配置名称" width="150" />
        <el-table-column prop="api_endpoint" label="API地址" width="250" show-overflow-tooltip />
        <el-table-column prop="region_id" label="地域ID" width="120" />
        <el-table-column prop="access_key_id" label="AccessKey ID" width="200" show-overflow-tooltip />
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
        label-width="120px"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入配置名称" />
          <div class="form-help">用于区分不同的配置，如：生产环境、测试环境</div>
        </el-form-item>
        
        <el-form-item label="API地址" prop="api_endpoint">
          <el-input v-model="form.api_endpoint" placeholder="例如: https://sas.cn-hangzhou.aliyuncs.com" />
        </el-form-item>
        
        <el-form-item label="AccessKey ID" prop="access_key_id">
          <el-input v-model="form.access_key_id" placeholder="请输入AccessKey ID" />
        </el-form-item>
        
        <el-form-item label="AccessKey Secret" prop="access_key_secret">
          <el-input
            v-model="form.access_key_secret"
            type="password"
            placeholder="请输入AccessKey Secret"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="地域ID" prop="region_id">
          <el-select v-model="form.region_id" placeholder="请选择地域" style="width: 100%">
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
import { aliyunConfigApi } from '../api/aliyunConfig'

export default {
  name: 'AliyunConfig',
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
      api_endpoint: 'https://sas.cn-hangzhou.aliyuncs.com',
      access_key_id: '',
      access_key_secret: '',
      region_id: 'cn-hangzhou',
      is_default: false,
      is_active: true,
      description: ''
    })
    
    const rules = {
      name: [
        { required: true, message: '请输入配置名称', trigger: 'blur' }
      ],
      api_endpoint: [
        { required: true, message: '请输入API地址', trigger: 'blur' },
        { type: 'url', message: '请输入正确的URL格式', trigger: 'blur' }
      ],
      access_key_id: [
        { required: true, message: '请输入AccessKey ID', trigger: 'blur' }
      ],
      access_key_secret: [
        { required: true, message: '请输入AccessKey Secret', trigger: 'blur' }
      ],
      region_id: [
        { required: true, message: '请选择地域ID', trigger: 'change' }
      ]
    }
    
    const loadConfigs = async () => {
      loading.value = true
      try {
        const response = await aliyunConfigApi.getConfigs()
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
        access_key_secret: ''  // 不显示原有Secret
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
        if (isEdit.value && !data.access_key_secret) {
          delete data.access_key_secret
        }
        
        if (isEdit.value) {
          await aliyunConfigApi.updateConfig(form.id, data)
          ElMessage.success('更新成功')
        } else {
          await aliyunConfigApi.createConfig(data)
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
        
        await aliyunConfigApi.deleteConfig(row.id)
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
        await aliyunConfigApi.setDefault(row.id)
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
        api_endpoint: 'https://sas.cn-hangzhou.aliyuncs.com',
        access_key_id: '',
        access_key_secret: '',
        region_id: 'cn-hangzhou',
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





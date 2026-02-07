# AWS Inspector V2 资产指纹数据导入插件使用说明

## 插件概述

`data_aws_inspector.py` 是一个数据记录类插件，用于从 AWS Inspector V2 获取 EC2 实例的资产指纹数据并导入到 Bifang 数据库中。

## 支持的资产类型

插件支持导入以下资产类型：

1. **server** - EC2实例（服务器）
2. **software** - 软件包（通过SBOM获取）

## 配置说明

### 必需配置项

- **access_key_id** (string): AWS Access Key ID
- **secret_access_key** (string): AWS Secret Access Key
- **region** (string, 可选): AWS区域，默认为 `ap-northeast-1` (东京)

### 可选配置项

- **session_token** (string, 可选): AWS Session Token（临时凭证，可选）
- **asset_types** (list, 可选): 要导入的资产类型列表。如果不指定，则导入所有资产类型。
  - 示例: `["server", "software"]`
- **page_size** (int, 可选): 分页大小，默认为 100

### 配置示例

```json
{
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "region": "ap-northeast-1",
  "asset_types": ["server", "software"],
  "page_size": 100
}
```

## AWS IAM 权限要求

**重要**：确保您的 AWS IAM 用户/角色具有以下权限：

### 必需的 IAM 策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "inspector2:ListCoverage",
        "inspector2:ListFindings",
        "inspector2:GetFindings",
        "inspector2:BatchGetFindings"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeImages"
      ],
      "Resource": "*"
    }
  ]
}
```

### 最小权限策略（如果只需要读取）

如果您只需要读取 Inspector 数据，可以使用以下最小权限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "inspector2:ListCoverage",
        "inspector2:ListFindings",
        "inspector2:BatchGetFindings",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

### 如何配置 IAM 权限

1. 登录 AWS 控制台
2. 进入 IAM 服务
3. 选择用户或角色
4. 点击"添加权限" -> "创建内联策略"
5. 使用 JSON 编辑器，粘贴上面的策略
6. 保存策略

## 使用方法

### 1. 创建 AWS 配置

1. 登录系统，进入"系统配置"页面或访问 `/aws-config` 路由
2. 点击"新建配置"
3. 填写以下信息：
   - **配置名称**: 例如 "AWS生产环境"
   - **Access Key ID**: AWS Access Key ID
   - **Secret Access Key**: AWS Secret Access Key
   - **区域**: 选择 AWS 区域（例如：ap-northeast-1 表示东京）
   - **Session Token**: （可选）如果使用临时凭证
4. 保存配置

### 2. 创建任务

1. 进入"任务管理"页面
2. 点击"新建任务"
3. 选择插件：`data_aws_inspector`
4. 选择 AWS 配置（如果不选择，将使用默认配置）
5. 设置触发类型：
   - **手动执行**: 需要时手动点击执行
   - **定时执行**: 设置 Cron 表达式，例如 `0 0 * * *` 表示每天0点执行
6. 填写配置 JSON（如果已在 AWS 配置中填写凭证，这里只需填写插件特定配置）：
   ```json
   {
     "asset_types": ["server", "software"],
     "page_size": 100
   }
   ```
7. 保存任务

### 3. 执行任务

- **手动执行**: 在任务列表页面点击"执行"按钮
- **定时执行**: 系统会根据 Cron 表达式自动执行

### 4. 查看导入结果

- 在任务列表页面点击"历史"查看执行记录
- 在"资产数据"页面查看导入的资产数据
- 可以通过 `source='aws_inspector'` 筛选 AWS 资产

## 执行结果说明

插件执行完成后会返回以下信息：

```json
{
  "success": true,
  "message": "导入完成: 成功 10 条，失败 0 条",
  "data": {
    "servers": {
      "imported": 5,
      "failed": 0
    },
    "software": {
      "imported": 5,
      "failed": 0
    },
    "summary": {
      "total_imported": 10,
      "total_failed": 0
    }
  }
}
```

## 注意事项

1. **权限要求**: 
   - 确保 AWS Access Key 具有 Inspector2 和 EC2 的读取权限
   - 参考上面的 IAM 权限配置

2. **区域设置**: 
   - 确保区域设置正确（例如：`ap-northeast-1` 表示亚太地区东京）
   - 区域必须与您的 AWS 资源所在区域一致

3. **API 限制**: 
   - AWS API 可能有频率限制
   - 如果数据量较大，建议适当调整 `page_size`
   - 使用定时任务避免高峰期

4. **数据更新**: 
   - 插件使用 `update_or_create` 方法，相同 UUID 的资产会被更新
   - 建议定期执行任务以保持数据最新

5. **临时凭证**: 
   - 如果使用临时凭证（如通过 STS），需要提供 `session_token`
   - 临时凭证有有效期，过期后需要更新

## 故障排查

### 问题1: 执行失败，提示 "UnrecognizedClientException: The security token included in the request is invalid"

**可能的原因**：
1. Access Key ID 或 Secret Access Key 不正确
2. 凭证已过期或被禁用
3. IAM 用户/角色没有 Inspector2 权限
4. 区域配置不正确

**解决方案**：
1. 检查 AWS 配置中的凭证是否正确
2. 在 AWS 控制台验证 Access Key 是否有效
3. 确认 IAM 用户/角色具有必需的权限（参考上面的 IAM 权限配置）
4. 确认区域设置正确（例如：`ap-northeast-1` 表示东京）

### 问题2: 执行失败，提示 "AccessDeniedException"

**解决方案**：
- 检查 IAM 用户/角色是否具有以下权限：
  - `inspector2:ListCoverage`
  - `inspector2:ListFindings`
  - `inspector2:GetFindings`
  - `inspector2:BatchGetFindings`
  - `ec2:DescribeInstances`
- 参考上面的 IAM 权限配置添加权限

### 问题3: 导入的资产数据为空

**解决方案**：
- 检查 AWS Inspector 是否已启用并扫描了资源
- 在 AWS 控制台查看 Inspector 是否有覆盖的资源
- 检查 `asset_types` 配置是否正确
- 查看执行日志了解详细错误信息

### 问题4: 插件执行失败，提示 "boto3未安装"

**解决方案**：
```bash
pip install boto3
# 或
pip3 install boto3
```

## API 参考

插件使用的 AWS Inspector V2 API：

- `ListCoverage` - 获取覆盖的资源列表
- `ListFindings` - 获取发现项列表
- `BatchGetFindings` - 批量获取发现项详情
- `DescribeInstances` (EC2) - 获取 EC2 实例详细信息

更多 API 文档请参考：[AWS Inspector V2 API 文档](https://docs.aws.amazon.com/inspector/v2/APIReference/Welcome.html)

## 区域代码参考

常用 AWS 区域代码：

- `ap-northeast-1` - 亚太地区（东京）
- `ap-northeast-2` - 亚太地区（首尔）
- `ap-southeast-1` - 亚太地区（新加坡）
- `ap-southeast-2` - 亚太地区（悉尼）
- `us-east-1` - 美国东部（弗吉尼亚北部）
- `us-west-2` - 美国西部（俄勒冈）
- `eu-west-1` - 欧洲（爱尔兰）

完整区域列表请参考：[AWS 区域和终端节点](https://docs.aws.amazon.com/general/latest/gr/rande.html)



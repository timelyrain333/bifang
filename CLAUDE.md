# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bifang is a cloud-based network security threat awareness system built with Django REST Framework backend and Vue.js 3 frontend. The system uses a plugin-based architecture to collect security assets from cloud providers (Aliyun, AWS), perform vulnerability intelligence gathering, and provide real-time alerting through DingTalk/Feishu integrations.

## Architecture

### Backend (Django)
- **API Layer**: Django REST Framework ViewSets in `app/views.py`
- **Task Processing**: Celery workers with Redis broker for async task execution
- **Data Models**: Task/Plugin/Asset models in `app/models.py`
- **Real-time Updates**: Server-Sent Events (SSE) via `app/utils/sse_manager.py`

### Frontend (Vue.js)
- **UI Framework**: Element Plus component library
- **State Management**: Pinia (see `frontend/src/stores/`)
- **API Client**: Axios with centralized configuration in `frontend/src/api/`

### Plugin System
The core extensibility mechanism is the plugin system in `app/plugins/`:

- **Base Plugin**: All plugins inherit from `BasePlugin` in `app/lib/base_plugin.py`
- **Plugin Types**:
  - `data_*`: Import assets from cloud APIs (e.g., `data_aliyun_security.py`, `data_aws_inspector.py`)
  - `collect_*`: Collect external vulnerability data (e.g., `collect_cnvd_list.py`)
  - `risk_*`: Risk detection and analysis
  - `dump_*`: Data export functionality
  - `alarm_*`: Alert notifications to DingTalk/Feishu

- **Plugin Loading**: Use `python manage.py load_plugins` to register plugins in the database
- **Execution**: Plugins are instantiated dynamically by Celery tasks in `app/tasks.py`

### AI/Agent Integration
- **SecOps Agent**: Natural language interface for security operations (`app/services/secops_agent.py`)
- **HexStrike AI**: External AI service for security assessment (port 8888)
- **Qianwen/通义千问**: AI-powered vulnerability analysis

## Development Commands

### Backend Development
```bash
# Run Django development server
python manage.py runserver 0.0.0.0:8000

# Database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load plugins into database
python manage.py load_plugins

# Start Celery worker (separate terminal)
celery -A app.celery_app worker -l info

# Start Celery beat scheduler (separate terminal)
celery -A app.celery_app beat -l info
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Development server (port 8080)
npm run serve

# Production build
npm run build

# Lint code
npm run lint
```

### Docker Deployment
```bash
# Start all services (backend, frontend, redis, celery, hexstrike-ai)
docker compose up -d --build

# Stop all services
docker compose down

# Restart specific service
docker compose restart backend

# View logs
docker compose logs -f backend
docker compose logs -f celery-worker
```

### Service Ports
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000/api/
- Django Admin: http://localhost:8000/admin/
- Redis: localhost:6379
- HexStrike AI: http://localhost:8888

## Key Data Flow

1. **Task Creation**: User creates task via frontend → Django API → Task stored in database
2. **Task Execution**: Celery Beat (scheduled) or manual trigger → Celery Worker
3. **Plugin Loading**: Worker loads plugin module dynamically from `app/plugins/`
4. **Plugin Execution**: Plugin's `execute()` method called with cloud provider credentials
5. **Data Collection**: Plugin fetches data from cloud APIs → saves to Asset model
6. **Status Updates**: Real-time SSE updates sent to frontend via `app/utils/sse_manager.py`
7. **Results**: Assets displayed in frontend with filtering and search

## Important File Locations

### Backend Core
- `app/models.py` - Django models (Task, Plugin, Asset, Vulnerability, AliyunConfig, AWSConfig)
- `app/views.py` - API ViewSets for all resources
- `app/tasks.py` - Celery task definitions and plugin execution logic
- `app/celery_app.py` - Celery application configuration
- `bifang/settings.py` - Django settings
- `bifang/urls.py` - Main URL routing

### Plugin Development
- `app/lib/base_plugin.py` - Base plugin class (inherit from this)
- `app/lib/db_helper.py` - Database helper utilities for plugins
- `app/lib/aliyun_client.py` - Aliyun API client wrapper
- `app/plugins/` - Plugin implementations
- `app/management/commands/load_plugins.py` - Plugin loading command

### Frontend
- `frontend/src/main.js` - Vue app entry point
- `frontend/src/router/index.js` - Route configuration
- `frontend/src/api/` - API client modules (task.js, plugin.js, etc.)
- `frontend/src/views/` - Page components

### Services
- `app/services/secops_agent.py` - AI-powered security operations agent
- `app/services/hexstrike_client.py` - HexStrike AI integration
- `app/utils/sse_manager.py` - Server-Sent Events for real-time updates

## Plugin Development

When creating a new plugin:

1. Create plugin file in `app/plugins/your_plugin_name.py`
2. Inherit from `BasePlugin`:
   ```python
   from app.lib.base_plugin import BasePlugin

   class Plugin(BasePlugin):
       def execute(self, *args, **kwargs):
           # Your plugin logic here
           return {
               'success': True,
               'message': '执行成功',
               'data': {}
           }
   ```
3. Run `python manage.py load_plugins` to register in database
4. Configuration is passed as `self.config` dictionary
5. Use `self.log_info()`, `self.log_error()`, `self.log_warning()` for logging
6. Use `DBHelper` from `app.lib.db_helper` for database operations

## Task Execution Model

- **Task**: Represents a scheduled or manual job with plugin configuration
- **TaskExecution**: Records each execution run with status, logs, and results
- **Status Flow**: pending → running → success/failed
- **Trigger Types**:
  - `manual`: User-triggered execution
  - `cron`: Scheduled execution using cron expressions
  - `interval`: Repeated execution at fixed intervals

## Cloud Provider Configuration

Credentials are stored in database models:
- **AliyunConfig**: AccessKeyId, AccessKeySecret, RegionId, DingTalk/Feishu webhooks
- **AWSConfig**: AccessKeyId, SecretAccessKey, SessionToken, Region

Configs are automatically merged into plugin execution context at runtime.

## Database Schema

Key models:
- **Plugin**: name, plugin_type, description, file_path, is_active
- **Task**: name, plugin_id, status, trigger_type, cron_expression, config (JSON), is_active
- **TaskExecution**: task_id, status, started_at, finished_at, result (JSON), error_message, logs
- **Asset**: asset_type, uuid, host_uuid, name, data (JSON), source, collected_at
- **Vulnerability**: cve_id, cnvd_id, title, description, publish_date, source

## Testing

No automated test suite is currently set up. Manual testing through the web interface is required.

## Deployment Considerations

- SQLite is default; switch to MySQL/PostgreSQL for production
- Ensure Redis is running before starting Celery workers
- Configure `ALLOWED_HOSTS` in production
- Use environment variables for sensitive configuration
- HexStrike AI service must be accessible from backend
- DingTalk/Feishu webhooks require external connectivity

## Troubleshooting

- **Tasks stuck in running state**: Check if Celery worker is running, use `python manage.py fix_stuck_executions`
- **Plugin not loading**: Run `python manage.py load_plugins` and check file path in database
- **SSE not working**: Ensure Redis is running and frontend is connected to correct backend URL
- **DingTalk/Feishu not receiving alerts**: Verify webhook URLs in AliyunConfig/AWSConfig
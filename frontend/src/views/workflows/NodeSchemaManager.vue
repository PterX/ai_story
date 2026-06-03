<template>
  <div :class="embedded ? 'node-schema-embedded' : 'page-shell node-schema-list'">
    <template v-if="!embedded">
      <div class="page-header">
        <div class="page-header-main">
          <h1 class="page-title">
            节点结构定义
          </h1>
          <p class="page-subtitle">
            管理节点结构、系统提示词与子图展开模板
          </p>
        </div>
        <div class="header-actions">
          <button
            class="primary-action"
            @click="handleCreate"
          >
            <span>新建节点结构定义</span>
          </button>
        </div>
      </div>
    </template>

    <div class="filter-card">
      <div class="search-box">
        <svg
          class="search-icon"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          v-model="filters.search"
          type="text"
          placeholder="搜索 key / 名称 / 描述..."
          class="search-input"
          @input="handleSearch"
        >
      </div>
      <div class="status-filters">
        <button
          v-for="option in statusOptions"
          :key="option.value"
          :class="['status-filter-btn', { active: filters.is_active === option.value }]"
          @click="handleStatusFilter(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <loading-container
      :loading="loading"
      class="loading-container"
    >
      <div
        v-if="schemas.length === 0"
        class="empty-state"
      >
        <div class="empty-hero">
          暂无节点结构定义
        </div>
        <p class="empty-hint">
          先定义节点结构，再配置系统提示词、输出解析和子图模板
        </p>
        <div class="empty-actions">
          <button
            class="primary-action"
            @click="handleCreate"
          >
            新建节点结构定义
          </button>
        </div>
      </div>

      <div
        v-else
        class="card-grid"
      >
        <article
          v-for="schema in schemas"
          :key="schema.id"
          class="data-card"
          @click="handleEdit(schema)"
        >
          <div class="card-top">
            <div class="card-main">
              <h3 class="card-title">
                {{ schema.name }}
              </h3>
              <code class="schema-key-label">{{ schema.key }}</code>
            </div>
            <span
              class="badge badge-sm card-type-badge"
              :class="schema.is_active ? 'badge-success' : 'badge-info'"
            >
              {{ schema.is_active ? '已启用' : '已停用' }}
            </span>
          </div>

          <p
            v-if="schema.description"
            class="card-desc"
          >
            {{ schema.description }}
          </p>

          <div class="card-footer">
            <div
              class="card-actions"
              @click.stop
            >
              <button
                class="btn btn-sm ghost-action"
                @click.stop="handleToggleStatus(schema)"
              >
                {{ schema.is_active ? '停用' : '启用' }}
              </button>
              <button
                class="btn btn-sm ghost-action danger"
                @click.stop="handleDelete(schema)"
              >
                删除
              </button>
            </div>
          </div>
        </article>
      </div>
    </loading-container>
  </div>
</template>

<script>
import LoadingContainer from '@/components/common/LoadingContainer.vue'
import { workflowNodeSchemaApi } from '@/api/workflows'

const FILTER_STORAGE_KEY = 'node_schema_list_filters'

const getSavedFilters = () => {
  const defaults = {
    search: '',
    is_active: ''
  }

  try {
    const saved = localStorage.getItem(FILTER_STORAGE_KEY)
    if (!saved) {
      return defaults
    }

    const parsed = JSON.parse(saved)
    return {
      search: typeof parsed.search === 'string' ? parsed.search : '',
      is_active: typeof parsed.is_active === 'string' ? parsed.is_active : ''
    }
  } catch (error) {
    return defaults
  }
}

export default {
  name: 'NodeSchemaManager',
  components: {
    LoadingContainer
  },
  props: {
    embedded: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      filters: getSavedFilters(),
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '已启用', value: 'true' },
        { label: '已停用', value: 'false' }
      ],
      schemas: [],
      loading: false,
      searchTimer: null
    }
  },
  created() {
    this.loadSchemas()
  },
  beforeDestroy() {
    clearTimeout(this.searchTimer)
  },
  methods: {
    async loadSchemas() {
      this.loading = true

      try {
        const response = await workflowNodeSchemaApi.getList(this.getFilterParams())
        this.schemas = Array.isArray(response?.results) ? response.results : (Array.isArray(response) ? response : [])
      } catch (error) {
        console.error('加载节点结构定义失败:', error)
        this.$message?.error('加载节点结构定义失败')
        this.schemas = []
      } finally {
        this.loading = false
      }
    },

    getFilterParams() {
      const params = {}
      if (this.filters.search) {
        params.search = this.filters.search
      }
      if (this.filters.is_active !== '') {
        params.is_active = this.filters.is_active === 'true'
      }
      return params
    },

    persistFilters() {
      try {
        localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(this.filters))
      } catch (error) {
        console.error('保存节点结构筛选条件失败:', error)
      }
    },

    handleSearch() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => {
        this.persistFilters()
        this.loadSchemas()
      }, 500)
    },

    handleStatusFilter(value) {
      this.filters.is_active = value
      this.persistFilters()
      this.loadSchemas()
    },

    handleCreate() {
      this.$router.push({ name: 'NodeSchemaCreate' })
    },

    handleEdit(schema) {
      this.$router.push({ name: 'NodeSchemaEdit', params: { id: schema.id } })
    },

    async handleToggleStatus(schema) {
      try {
        await workflowNodeSchemaApi.patch(schema.id, {
          is_active: !schema.is_active
        })
        this.$message?.success(`节点结构定义已${schema.is_active ? '停用' : '启用'}`)
        await this.loadSchemas()
      } catch (error) {
        console.error('切换状态失败:', error)
        this.$message?.error('切换状态失败')
      }
    },

    async handleDelete(schema) {
      const confirmed = await this.$confirm(
        `确定要删除节点结构定义 "${schema.name}" 吗?`,
        '删除节点结构定义',
        { tone: 'danger', confirmText: '删除' }
      )

      if (!confirmed) {
        return
      }

      try {
        await workflowNodeSchemaApi.delete(schema.id)
        await this.$alert('删除成功', '操作完成', { tone: 'success' })
        await this.loadSchemas()
      } catch (error) {
        console.error('删除节点结构定义失败:', error)
        await this.$alert('删除失败', '操作失败', { tone: 'error' })
      }
    },

  }
}
</script>

<style scoped>
.page-shell {
  min-height: 100vh;
  padding: 2.5rem 3.5rem 3rem;
  background: transparent;
}

.node-schema-embedded {
  background: transparent;
}

.loading-container {
  display: block;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.page-header-main {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.page-title {
  font-size: 2.2rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
  letter-spacing: -0.02em;
}

.layout-shell.theme-dark .page-title {
  color: #e2e8f0;
}

.page-subtitle {
  font-size: 0.95rem;
  color: #64748b;
  margin: 0;
}

.layout-shell.theme-dark .page-subtitle {
  color: #94a3b8;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #ffffff;
  color: #0f172a;
}

.layout-shell.theme-dark .primary-action {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.25);
  color: #e2e8f0;
}

.primary-action:hover {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 12px 24px rgba(20, 184, 166, 0.18);
  transform: translateY(-1px);
}

.layout-shell.theme-dark .primary-action:hover {
  border-color: rgba(94, 234, 212, 0.6);
  box-shadow: 0 12px 24px rgba(2, 6, 23, 0.55);
}

.filter-card {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 1rem 1.25rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
  margin-bottom: 2.5rem;
  backdrop-filter: blur(10px);
}

.layout-shell.theme-dark .filter-card {
  background: rgba(15, 23, 42, 0.86);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(2, 6, 23, 0.55);
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 280px;
  max-width: 460px;
}

.search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1.25rem;
  height: 1.25rem;
  color: #94a3b8;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.75rem 1rem 0.75rem 3rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  outline: none;
}

.layout-shell.theme-dark .search-input {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.25);
  color: #e2e8f0;
}

.search-input:focus {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
}

.search-input::placeholder {
  color: #cbd5e1;
}

.layout-shell.theme-dark .search-input::placeholder {
  color: #64748b;
}

.status-filters {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.status-filter-btn {
  padding: 0.625rem 1.25rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.9);
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 500;
  outline: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.layout-shell.theme-dark .status-filter-btn {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
}

.status-filter-btn.active {
  background: rgba(20, 184, 166, 0.16);
  color: #0f172a;
  border-color: rgba(20, 184, 166, 0.5);
}

.layout-shell.theme-dark .status-filter-btn.active {
  background: rgba(94, 234, 212, 0.2);
  color: #e2e8f0;
  border-color: rgba(94, 234, 212, 0.5);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

.data-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.1rem;
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.7) 0%, rgba(14, 165, 233, 0.7) 100%) 0 0 / 0 3px no-repeat,
    rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
  transition: all 0.3s ease;
  cursor: pointer;
}

.layout-shell.theme-dark .data-card {
  background: linear-gradient(90deg, rgba(94, 234, 212, 0.5) 0%, rgba(56, 189, 248, 0.5) 100%) 0 0 / 0 3px no-repeat,
    rgba(15, 23, 42, 0.92);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(2, 6, 23, 0.55);
}

.data-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
  border-color: rgba(148, 163, 184, 0.35);
  background-size: 100% 3px, auto;
}

.layout-shell.theme-dark .data-card:hover {
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.6);
}

.card-top,
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.card-footer {
  margin-top: auto;
}

.card-main {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.card-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #0f172a;
}

.layout-shell.theme-dark .card-title {
  color: #e2e8f0;
}

.card-desc {
  margin: 0;
  color: #64748b;
  font-size: 0.85rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.layout-shell.theme-dark .card-desc {
  color: #94a3b8;
}

.schema-key-label {
  display: inline-block;
  font-size: 0.8rem;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.12);
  color: #64748b;
  margin-top: 0.25rem;
}

.layout-shell.theme-dark .schema-key-label {
  color: #94a3b8;
}

.card-actions {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.ghost-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.84);
  color: #334155;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.layout-shell.theme-dark .ghost-action {
  background: rgba(15, 23, 42, 0.84);
  border-color: rgba(148, 163, 184, 0.24);
  color: #e2e8f0;
}

.ghost-action:hover {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 12px 24px rgba(20, 184, 166, 0.18);
  transform: translateY(-1px);
}

.ghost-action.danger {
  color: #dc2626;
}

.card-type-badge {
  align-self: flex-start;
}

.empty-state {
  padding: 3.5rem 2rem;
  border-radius: 22px;
  text-align: center;
  background: rgba(255, 255, 255, 0.88);
  border: 1px dashed rgba(148, 163, 184, 0.35);
}

.layout-shell.theme-dark .empty-state {
  background: rgba(15, 23, 42, 0.88);
  border-color: rgba(148, 163, 184, 0.3);
}

.empty-hero {
  font-size: 1.4rem;
  font-weight: 600;
  color: #0f172a;
}

.layout-shell.theme-dark .empty-hero {
  color: #e2e8f0;
}

.empty-hint {
  margin: 0.8rem 0 0;
  color: #64748b;
}

.empty-actions {
  margin-top: 1.5rem;
}

@media (max-width: 768px) {
  .page-shell {
    padding: 2rem 1.5rem;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
  }

  .primary-action {
    width: 100%;
  }

  .search-box {
    min-width: 100%;
  }
}
</style>

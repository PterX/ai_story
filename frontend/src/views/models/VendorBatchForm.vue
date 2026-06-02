<template>
  <div class="page-shell vendor-batch-form">
    <div class="page-header">
      <div class="page-header-main">
        <h1 class="page-title">
          批量添加厂商模型
        </h1>
        <p class="page-subtitle">
          选择内置厂商，填写 API Key，拉取模型列表后批量创建
        </p>
      </div>
      <div class="header-actions">
        <button
          class="secondary-outline-action"
          :disabled="discovering || submitting"
          @click="handleBack"
        >
          返回列表
        </button>
      </div>
    </div>

    <div class="content-grid">
      <section class="panel-card form-card">
        <div class="card-top">
          <div>
            <h2 class="card-title">
              厂商配置
            </h2>
            <p class="card-desc">
              系统内置固定厂商地址，可按模型能力分别拉取并批量创建
            </p>
          </div>
          <span class="pill">内置厂商</span>
        </div>

        <div class="form-grid">
          <label class="field-block">
            <span class="field-label">模型厂商</span>
            <select
              v-model="form.vendor"
              class="field-input"
            >
              <option value="">请选择厂商</option>
              <option
                v-for="vendor in vendors"
                :key="vendor.key"
                :value="vendor.key"
              >
                {{ vendor.label }}
              </option>
            </select>
          </label>

          <label class="field-block">
            <span class="field-label">模型能力</span>
            <select
              v-model="form.capability"
              class="field-input"
              :disabled="!availableCapabilities.length"
            >
              <option
                v-for="capability in availableCapabilities"
                :key="capability.key"
                :value="capability.key"
              >
                {{ getProviderTypeLabel(capability.provider_type) }}
              </option>
            </select>
          </label>

          <label class="field-block field-block-wide">
            <span class="field-label">API Key</span>
            <input
              v-model.trim="form.api_key"
              type="password"
              autocomplete="new-password"
              class="field-input"
              placeholder="请输入该厂商 API Key"
            >
          </label>
        </div>

        <div
          v-if="selectedVendor"
          class="vendor-summary"
        >
          <div class="summary-item">
            <span class="summary-label">厂商</span>
            <span class="summary-value">{{ selectedVendor.label }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">能力</span>
            <span class="summary-value">{{ selectedCapability ? getProviderTypeLabel(selectedCapability.provider_type) : '--' }}</span>
          </div>
          <div class="summary-item summary-item-wide">
            <span class="summary-label">固定地址</span>
            <span class="summary-value summary-url">{{ selectedCapability ? selectedCapability.api_url : '--' }}</span>
          </div>
        </div>

        <div class="discover-actions">
          <button
            class="primary-action"
            :disabled="discovering || !canDiscover"
            @click="handleDiscover"
          >
            {{ discovering ? '拉取中...' : '拉取模型列表' }}
          </button>
        </div>
      </section>

      <section class="panel-card setting-card">
        <div class="card-top">
          <div>
            <h2 class="card-title">
              批量创建默认配置
            </h2>
            <p class="card-desc">
              这些配置会应用到本次创建的全部模型
            </p>
          </div>
        </div>

        <div class="form-grid compact-grid">
          <label class="field-block">
            <span class="field-label">超时(秒)</span>
            <input
              v-model.number="form.timeout"
              type="number"
              min="1"
              max="600"
              class="field-input"
            >
          </label>
          <label class="field-block">
            <span class="field-label">最大 Token</span>
            <input
              v-model.number="form.max_tokens"
              type="number"
              min="1"
              class="field-input"
            >
          </label>
          <label class="field-block">
            <span class="field-label">Temperature</span>
            <input
              v-model.number="form.temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
              class="field-input"
            >
          </label>
          <label class="field-block">
            <span class="field-label">Top P</span>
            <input
              v-model.number="form.top_p"
              type="number"
              min="0"
              max="1"
              step="0.1"
              class="field-input"
            >
          </label>
          <label class="field-block">
            <span class="field-label">每分钟限制</span>
            <input
              v-model.number="form.rate_limit_rpm"
              type="number"
              min="1"
              class="field-input"
            >
          </label>
          <label class="field-block">
            <span class="field-label">每天限制</span>
            <input
              v-model.number="form.rate_limit_rpd"
              type="number"
              min="1"
              class="field-input"
            >
          </label>
        </div>

        <label class="toggle-row">
          <input
            v-model="form.is_active"
            type="checkbox"
          >
          <span>{{ form.is_active ? '创建后默认激活' : '创建后默认停用' }}</span>
        </label>
      </section>
    </div>

    <section class="panel-card result-card">
      <div class="card-top">
        <div>
          <h2 class="card-title">
            可创建模型
          </h2>
          <p class="card-desc">
            已选 {{ selectedModelNames.length }} / {{ visibleModels.length }} 个模型
          </p>
        </div>
        <div class="result-actions result-actions-wide">
          <div
            v-if="discoveredModels.length"
            class="status-filters"
          >
            <button
              class="status-filter-btn"
              :class="{ active: modelFilterMode === 'recommended' }"
              @click="setModelFilterMode('recommended')"
            >
              推荐模型
            </button>
            <button
              class="status-filter-btn"
              :class="{ active: modelFilterMode === 'all' }"
              @click="setModelFilterMode('all')"
            >
              全部模型
            </button>
          </div>
          <button
            class="ghost-action"
            :disabled="!visibleModels.length"
            @click="selectAll"
          >
            全选
          </button>
          <button
            class="ghost-action"
            :disabled="!selectedModelNames.length"
            @click="clearSelection"
          >
            清空
          </button>
          <button
            class="primary-action"
            :disabled="submitting || !selectedModelNames.length || !form.vendor || !form.api_key"
            @click="handleBatchCreate"
          >
            {{ submitting ? '创建中...' : '批量创建选中模型' }}
          </button>
        </div>
      </div>

      <div
        v-if="!discoveredModels.length"
        class="empty-state"
      >
        <div class="empty-hero">
          还没有模型列表
        </div>
        <p class="empty-hint">
          先选择厂商、模型能力并填写 API Key，再拉取该能力下可用模型
        </p>
      </div>

      <div
        v-else
        class="model-grid"
      >
        <label
          v-for="model in visibleModels"
          :key="model.id"
          class="model-option"
          :class="{ selected: selectedModelNames.includes(model.id) }"
        >
          <input
            v-model="selectedModelNames"
            type="checkbox"
            :value="model.id"
          >
          <div class="model-option-main">
            <div class="model-option-title">
              {{ model.name || model.id }}
              <span
                v-if="model.is_recommended"
                class="recommend-badge"
              >推荐</span>
            </div>
            <div class="model-option-desc">{{ model.id }}</div>
          </div>
        </label>
      </div>
    </section>

    <section
      v-if="submitResult"
      class="panel-card summary-card"
    >
      <div class="card-top">
        <div>
          <h2 class="card-title">
            创建结果
          </h2>
          <p class="card-desc">
            已创建 {{ submitResult.created_count }} 个，跳过 {{ submitResult.skipped_count }} 个
          </p>
        </div>
      </div>

      <div class="result-summary-grid">
        <div class="summary-pane">
          <div class="summary-pane-title">
            新建成功
          </div>
          <div
            v-if="submitResult.created && submitResult.created.length"
            class="tag-list"
          >
            <span
              v-for="item in submitResult.created"
              :key="item.id"
              class="result-tag success"
            >
              {{ item.model_name }}
            </span>
          </div>
          <p
            v-else
            class="empty-inline"
          >
            本次没有新增模型
          </p>
        </div>

        <div class="summary-pane">
          <div class="summary-pane-title">
            已跳过
          </div>
          <div
            v-if="submitResult.skipped && submitResult.skipped.length"
            class="tag-list"
          >
            <span
              v-for="item in submitResult.skipped"
              :key="`${item.model_name}-${item.id || item.name}`"
              class="result-tag muted-tag"
            >
              {{ item.model_name }}
            </span>
          </div>
          <p
            v-else
            class="empty-inline"
          >
            没有跳过项
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { modelProviderApi } from '@/api/models'

export default {
  name: 'VendorBatchForm',
  data() {
    return {
      vendors: [],
      form: {
        vendor: '',
        capability: 'llm',
        api_key: '',
        is_active: true,
        timeout: 60,
        max_tokens: 40960,
        temperature: 0.7,
        top_p: 1,
        rate_limit_rpm: 60,
        rate_limit_rpd: 1000,
        priority: 0
      },
      discoveredModels: [],
      selectedModelNames: [],
      modelFilterMode: 'recommended',
      discovering: false,
      submitting: false,
      submitResult: null
    }
  },
  computed: {
    selectedVendor() {
      return this.vendors.find((item) => item.key === this.form.vendor) || null
    },
    availableCapabilities() {
      return this.selectedVendor?.capabilities || []
    },
    selectedCapability() {
      return this.availableCapabilities.find((item) => item.key === this.form.capability) || null
    },
    canDiscover() {
      return Boolean(this.form.vendor && this.form.capability && this.form.api_key)
    },
    recommendedModels() {
      return this.discoveredModels.filter((item) => item.is_recommended)
    },
    visibleModels() {
      if (this.modelFilterMode === 'recommended' && this.recommendedModels.length) {
        return this.recommendedModels
      }
      return this.discoveredModels
    }
  },
  watch: {
    'form.vendor'(value) {
      const vendor = this.vendors.find((item) => item.key === value)
      const capabilities = vendor?.capabilities || []
      if (!capabilities.length) {
        this.form.capability = 'llm'
        return
      }
      if (!capabilities.some((item) => item.key === this.form.capability)) {
        this.form.capability = capabilities[0].key
      }
      this.discoveredModels = []
      this.selectedModelNames = []
      this.submitResult = null
    },
    'form.capability'() {
      this.discoveredModels = []
      this.selectedModelNames = []
      this.submitResult = null
    }
  },
  async created() {
    await this.loadVendors()
  },
  methods: {
    async loadVendors() {
      try {
        const response = await modelProviderApi.getBuiltinVendors()
        this.vendors = response.results || []
      } catch (error) {
        console.error('加载内置厂商失败:', error)
        await this.$alert('加载内置厂商失败', '加载失败', { tone: 'error' })
      }
    },

    async handleDiscover() {
      if (!this.canDiscover) {
        await this.$alert('请先选择厂商并填写 API Key', '提示', { tone: 'warning' })
        return
      }

      this.discovering = true
      this.submitResult = null
      try {
        const response = await modelProviderApi.discoverVendorModels({
          vendor: this.form.vendor,
          capability: this.form.capability,
          api_key: this.form.api_key
        })
        this.discoveredModels = response.models || []
        this.modelFilterMode = this.discoveredModels.some((item) => item.is_recommended) ? 'recommended' : 'all'
        const defaultModels = this.modelFilterMode === 'recommended'
          ? this.discoveredModels.filter((item) => item.is_recommended)
          : this.discoveredModels
        this.selectedModelNames = defaultModels.map((item) => item.id)
        if (!this.discoveredModels.length) {
          await this.$alert('当前厂商未返回可导入模型', '拉取完成', { tone: 'warning' })
        }
      } catch (error) {
        console.error('拉取模型列表失败:', error)
        await this.$alert(
          error.response?.data?.error || '拉取模型列表失败',
          '拉取失败',
          { tone: 'error' }
        )
      } finally {
        this.discovering = false
      }
    },

    setModelFilterMode(mode) {
      this.modelFilterMode = mode
      this.selectedModelNames = this.visibleModels.map((item) => item.id)
    },

    selectAll() {
      this.selectedModelNames = this.visibleModels.map((item) => item.id)
    },

    clearSelection() {
      this.selectedModelNames = []
    },

    async handleBatchCreate() {
      if (!this.selectedModelNames.length) {
        await this.$alert('请至少选择一个模型', '提示', { tone: 'warning' })
        return
      }

      this.submitting = true
      try {
        const response = await modelProviderApi.batchCreateVendorModels({
          vendor: this.form.vendor,
          capability: this.form.capability,
          api_key: this.form.api_key,
          model_names: this.selectedModelNames,
          is_active: this.form.is_active,
          timeout: this.form.timeout,
          max_tokens: this.form.max_tokens,
          temperature: this.form.temperature,
          top_p: this.form.top_p,
          rate_limit_rpm: this.form.rate_limit_rpm,
          rate_limit_rpd: this.form.rate_limit_rpd,
          priority: this.form.priority
        })
        this.submitResult = response
        await this.$alert(
          `创建完成：新增 ${response.created_count} 个，跳过 ${response.skipped_count} 个`,
          '操作完成',
          { tone: 'success' }
        )
      } catch (error) {
        console.error('批量创建模型失败:', error)
        await this.$alert(
          error.response?.data?.error || '批量创建模型失败',
          '创建失败',
          { tone: 'error' }
        )
      } finally {
        this.submitting = false
      }
    },

    handleBack() {
      this.$router.push({ name: 'ModelList' })
    },

    getProviderTypeLabel(type) {
      const labels = {
        llm: 'LLM',
        text2image: '文生图',
        image2video: '图生视频',
        image_edit: '图片编辑'
      }
      return labels[type] || type
    }
  }
}
</script>

<style scoped>
.page-shell {
  min-height: 100vh;
  padding: 2.5rem 3.5rem 3rem;
  background: transparent;
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
  gap: 0.75rem;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}

.panel-card {
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.7) 0%, rgba(14, 165, 233, 0.7) 100%) 0 0 / 0 3px no-repeat,
    rgba(255, 255, 255, 0.92);
  border-radius: 18px;
  padding: 1.35rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
}

.layout-shell.theme-dark .panel-card {
  background: linear-gradient(90deg, rgba(94, 234, 212, 0.5) 0%, rgba(56, 189, 248, 0.5) 100%) 0 0 / 0 3px no-repeat,
    rgba(15, 23, 42, 0.92);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(2, 6, 23, 0.55);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
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
  margin: 0.4rem 0 0;
  color: #64748b;
  font-size: 0.9rem;
}

.layout-shell.theme-dark .card-desc {
  color: #94a3b8;
}

.pill {
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: rgba(20, 184, 166, 0.16);
  color: #0f172a;
}

.layout-shell.theme-dark .pill {
  background: rgba(94, 234, 212, 0.22);
  color: #e2e8f0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.compact-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.field-block-wide {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 0.82rem;
  color: #64748b;
}

.layout-shell.theme-dark .field-label {
  color: #94a3b8;
}

.field-input {
  width: 100%;
  padding: 0.8rem 0.95rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  outline: none;
  transition: all 0.2s ease;
}

.layout-shell.theme-dark .field-input {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.22);
  color: #e2e8f0;
}

.field-input:focus {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
}

.vendor-summary,
.result-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.summary-item,
.summary-pane {
  background: rgba(148, 163, 184, 0.1);
  border-radius: 14px;
  padding: 0.85rem 1rem;
}

.layout-shell.theme-dark .summary-item,
.layout-shell.theme-dark .summary-pane {
  background: rgba(30, 41, 59, 0.6);
}

.summary-item-wide {
  grid-column: 1 / -1;
}

.summary-label,
.summary-pane-title {
  display: block;
  font-size: 0.78rem;
  color: #94a3b8;
  margin-bottom: 0.3rem;
}

.summary-value {
  color: #0f172a;
  font-weight: 600;
}

.layout-shell.theme-dark .summary-value {
  color: #e2e8f0;
}

.summary-url {
  word-break: break-all;
}

.discover-actions,
.result-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: center;
}

.result-actions-wide {
  justify-content: flex-end;
}

.status-filters {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-right: auto;
}

.status-filter-btn {
  padding: 0.5rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.9);
  color: #64748b;
  font-size: 0.84rem;
  font-weight: 500;
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

.result-card,
.summary-card {
  margin-top: 1.25rem;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.85rem;
}

.model-option {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.9rem 1rem;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.72);
  cursor: pointer;
  transition: all 0.2s ease;
}

.layout-shell.theme-dark .model-option {
  background: rgba(15, 23, 42, 0.72);
  border-color: rgba(148, 163, 184, 0.18);
}

.model-option.selected {
  border-color: rgba(20, 184, 166, 0.45);
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.12);
  transform: translateY(-2px);
}

.model-option-main {
  min-width: 0;
}

.model-option-title {
  color: #0f172a;
  font-weight: 600;
  word-break: break-word;
  display: flex;
  gap: 0.45rem;
  align-items: center;
  flex-wrap: wrap;
}

.layout-shell.theme-dark .model-option-title {
  color: #e2e8f0;
}

.model-option-desc {
  margin-top: 0.25rem;
  color: #64748b;
  font-size: 0.82rem;
  word-break: break-all;
}

.recommend-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  font-size: 0.72rem;
  background: rgba(20, 184, 166, 0.16);
  color: #0f766e;
}

.layout-shell.theme-dark .recommend-badge {
  background: rgba(94, 234, 212, 0.2);
  color: #99f6e4;
}

.layout-shell.theme-dark .model-option-desc {
  color: #94a3b8;
}

.primary-action,
.secondary-outline-action,
.ghost-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.72rem 1.35rem;
  border-radius: 999px;
  font-size: 0.92rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-action {
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #ffffff;
  color: #0f172a;
}

.secondary-outline-action,
.ghost-action {
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.85);
  color: #334155;
}

.layout-shell.theme-dark .primary-action,
.layout-shell.theme-dark .secondary-outline-action,
.layout-shell.theme-dark .ghost-action {
  background: rgba(15, 23, 42, 0.9);
  color: #e2e8f0;
  border-color: rgba(148, 163, 184, 0.24);
}

.primary-action:hover,
.secondary-outline-action:hover,
.ghost-action:hover {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 12px 24px rgba(20, 184, 166, 0.18);
  transform: translateY(-1px);
}

.toggle-row {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  margin-top: 1rem;
  color: #475569;
}

.layout-shell.theme-dark .toggle-row {
  color: #cbd5e1;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
}

.empty-hero {
  font-size: 1.2rem;
  font-weight: 600;
  color: #0f172a;
}

.layout-shell.theme-dark .empty-hero {
  color: #e2e8f0;
}

.empty-hint,
.empty-inline {
  color: #94a3b8;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.result-tag {
  display: inline-flex;
  align-items: center;
  padding: 0.38rem 0.7rem;
  border-radius: 999px;
  font-size: 0.82rem;
}

.result-tag.success {
  background: rgba(16, 185, 129, 0.14);
  color: #047857;
}

.result-tag.muted-tag {
  background: rgba(148, 163, 184, 0.16);
  color: #475569;
}

.layout-shell.theme-dark .result-tag.success {
  color: #86efac;
}

.layout-shell.theme-dark .result-tag.muted-tag {
  color: #cbd5e1;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-shell {
    padding: 2rem 1.5rem;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions,
  .discover-actions,
  .result-actions {
    width: 100%;
  }

  .primary-action,
  .secondary-outline-action,
  .ghost-action {
    width: 100%;
  }

  .form-grid,
  .compact-grid,
  .vendor-summary,
  .result-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>

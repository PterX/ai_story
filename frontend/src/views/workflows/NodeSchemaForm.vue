<template>
  <div class="page-shell node-schema-form">
    <div class="page-header">
      <div class="page-header-main">
        <h1 class="page-title">
          {{ isEdit ? '编辑节点结构定义' : '新建节点结构定义' }}
        </h1>
        <p class="page-subtitle">
          {{ isEdit ? '更新节点结构、提示词与子图模板' : '定义节点结构、系统提示词与子图展开模板' }}
        </p>
      </div>
      <div class="header-actions">
        <button
          class="secondary-outline-action"
          :disabled="submitting"
          @click="handleCancel"
        >
          返回列表
        </button>
      </div>
    </div>

    <loading-container :loading="loading">
      <form
        class="form-layout"
        @submit.prevent="handleSubmit"
      >
        <section class="panel-card">
          <div class="card-top">
            <div>
              <h2 class="card-title">
                基础信息
              </h2>
              <p class="card-desc">
                配置节点结构的名称、唯一标识与描述
              </p>
            </div>
            <span class="pill">必填</span>
          </div>

          <div class="form-grid">
            <label class="field-block">
              <span class="field-label">结构键 <em>*</em></span>
              <input
                v-model="formData.key"
                type="text"
                placeholder="例如: rewrite_node"
                class="field-input"
                required
                :disabled="isEdit"
              >
              <span class="field-hint">全局唯一的标识符，创建后不可修改</span>
            </label>

            <label class="field-block">
              <span class="field-label">名称 <em>*</em></span>
              <input
                v-model="formData.name"
                type="text"
                placeholder="例如: 文案改写节点"
                class="field-input"
                required
              >
            </label>

            <label class="field-block field-block-wide">
              <span class="field-label">描述</span>
              <textarea
                v-model="formData.description"
                placeholder="简要描述该节点结构的用途..."
                class="field-input field-textarea"
                rows="3"
              />
            </label>
          </div>
        </section>

        <section class="panel-card">
          <div class="card-top">
            <div>
              <h2 class="card-title">
                系统提示词
              </h2>
              <p class="card-desc">
                定义节点执行时使用的系统级提示词
              </p>
            </div>
          </div>

          <label class="field-block">
            <textarea
              v-model="formData.system_prompt"
              placeholder="输入系统提示词，支持 Jinja2 模板语法..."
              class="field-input field-textarea field-textarea-lg"
              rows="8"
            />
          </label>
        </section>

        <section class="panel-card">
          <div class="card-top">
            <div>
              <h2 class="card-title">
                结构配置 (schema_config)
              </h2>
              <p class="card-desc">
                定义输出结构与子图展开模板
              </p>
            </div>
          </div>

          <div class="subgraph-toolbar">
            <div class="toolbar-copy">
              <span class="field-label">子图模板</span>
              <span class="field-hint">每个输出 item 会按这里的模板生成一个子节点，只需要填写子节点的关键字段。</span>
            </div>
            <button
              type="button"
              class="secondary-outline-action compact-action"
              @click="addSubgraphTemplate"
            >
              添加子节点
            </button>
          </div>

          <div
            v-if="subgraphTemplates.length"
            class="template-list"
          >
            <div
              v-for="(template, index) in subgraphTemplates"
              :key="template.localId"
              class="template-item"
            >
              <div class="template-item-header">
                <strong>子节点 {{ index + 1 }}</strong>
                <button
                  type="button"
                  class="text-action"
                  @click="removeSubgraphTemplate(index)"
                >
                  删除
                </button>
              </div>

              <div class="form-grid">
                <label class="field-block">
                  <span class="field-label">子节点标识 <em>*</em></span>
                  <input
                    v-model="template.node_key"
                    type="text"
                    :placeholder="nodeKeyPlaceholder"
                    class="field-input"
                    required
                  >
                  <span class="field-hint">用于更新同一个子节点，可使用 {{ templateExample }}</span>
                </label>

                <label class="field-block">
                  <span class="field-label">节点类型 <em>*</em></span>
                  <select
                    v-model="template.node_type"
                    class="field-input"
                    required
                  >
                    <option
                      v-for="option in nodeTypeOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label class="field-block">
                  <span class="field-label">标题模板 (label)</span>
                  <input
                    v-model="template.title"
                    type="text"
                    :placeholder="titlePlaceholder"
                    class="field-input"
                  >
                </label>

                <label
                  v-if="template.node_type === 'rewrite'"
                  class="field-block"
                >
                  <span class="field-label">Text 模板 (text)</span>
                  <input
                    v-model="template.text"
                    type="text"
                    :placeholder="textPlaceholder"
                    class="field-input"
                  >
                  <span class="field-hint">保存到 data_mapping.text</span>
                </label>

                <label class="field-block">
                  <span class="field-label">Prompt 模板 (prompt)</span>
                  <input
                    v-model="template.prompt"
                    type="text"
                    :placeholder="promptPlaceholder"
                    class="field-input"
                  >
                  <span class="field-hint">保存到 data_mapping.prompt</span>
                </label>

                <label class="field-block">
                  <span class="field-label">连接关系</span>
                  <select
                    v-model="template.connect_source"
                    class="field-input"
                  >
                    <option value="">
                      不连线
                    </option>
                    <option value="$parent">
                      父节点
                    </option>
                    <option
                      v-for="option in getConnectionSourceOptions(index)"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                  <span class="field-hint">
                    选择一条连到当前子节点的来源节点，可连接父节点或其他子节点。
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div
            v-else
            class="empty-template"
          >
            暂无子节点模板
          </div>
        </section>

        <section class="panel-card">
          <div class="card-top">
            <div>
              <h2 class="card-title">
                状态
              </h2>
              <p class="card-desc">
                启用或停用该节点结构定义
              </p>
            </div>
          </div>

          <div class="form-grid">
            <label class="field-block">
              <span class="toggle-card">
                <span class="toggle-track">
                  <input
                    v-model="formData.is_active"
                    type="checkbox"
                  >
                  <span class="toggle-text">{{ formData.is_active ? '已启用' : '已停用' }}</span>
                </span>
              </span>
            </label>
          </div>
        </section>

        <div class="form-actions">
          <button
            type="submit"
            class="primary-action"
            :disabled="submitting"
          >
            <span>{{ submitting ? '保存中...' : '保存' }}</span>
          </button>
          <button
            type="button"
            class="secondary-outline-action"
            :disabled="submitting"
            @click="handleCancel"
          >
            取消
          </button>
        </div>
      </form>
    </loading-container>
  </div>
</template>

<script>
import LoadingContainer from '@/components/common/LoadingContainer.vue'
import { workflowNodeSchemaApi, createDefaultSchemaConfig } from '@/api/workflows'

const createSubgraphTemplate = (overrides = {}) => ({
  localId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  node_key: 'scene:{{ index }}',
  node_type: 'rewrite',
  title: '{{ item.label }}',
  text: '{{ item.text }}',
  prompt: '{{ item.prompt }}',
  connect_source: '$parent',
  rawNode: {},
  rawEdge: {},
  ...overrides
})

export default {
  name: 'NodeSchemaForm',
  components: {
    LoadingContainer
  },
  data() {
    return {
      formData: {
        key: '',
        name: '',
        description: '',
        system_prompt: '',
        is_active: true
      },
      schemaConfig: createDefaultSchemaConfig(),
      subgraphTemplates: [createSubgraphTemplate()],
      nodeTypeOptions: [
        { value: 'rewrite', label: '文本节点' },
        { value: 'image_generation', label: '图片节点' },
        { value: 'video_generation', label: '视频节点' }
      ],
      loading: false,
      submitting: false
    }
  },
  computed: {
    isEdit() {
      return !!this.$route.params.id
    },
    templateExample() {
      return '{{ index }} / {{ item.label }}'
    },
    nodeKeyPlaceholder() {
      return '例如: scene:{{ index }}'
    },
    titlePlaceholder() {
      return '例如: {{ item.label }}'
    },
    textPlaceholder() {
      return '例如: {{ item.text }}'
    },
    promptPlaceholder() {
      return '例如: {{ item.prompt }}'
    }
  },
  async created() {
    if (this.isEdit) {
      await this.loadSchema()
    }
  },
  methods: {
    async loadSchema() {
      this.loading = true
      try {
        const data = await workflowNodeSchemaApi.getDetail(this.$route.params.id)
        this.formData = {
          key: data.key || '',
          name: data.name || '',
          description: data.description || '',
          system_prompt: data.system_prompt || '',
          is_active: data.is_active !== false
        }
        if (data.schema_config) {
          this.schemaConfig = {
            ...this.schemaConfig,
            ...data.schema_config,
            output_schema: {
              ...this.schemaConfig.output_schema,
              ...(data.schema_config.output_schema || {})
            },
            materialization: {
              ...this.schemaConfig.materialization,
              ...(data.schema_config.materialization || {})
            }
          }
          this.subgraphTemplates = this.graphToTemplateForm(this.schemaConfig.materialization.graph)
        }
      } catch (error) {
        console.error('加载节点结构定义失败:', error)
        this.$message?.error('加载节点结构定义失败')
        this.$router.push({ name: 'NodeSchemaManager' })
      } finally {
        this.loading = false
      }
    },

    graphToTemplateForm(graph = {}) {
      const nodes = Array.isArray(graph.nodes) ? graph.nodes : []
      const edges = Array.isArray(graph.edges) ? graph.edges : []
      if (!nodes.length) {
        return [createSubgraphTemplate()]
      }

      return nodes
        .filter(node => node && typeof node === 'object')
        .map(node => {
          const nodeKey = String(node.node_key || node.key || '').trim()
          const incomingEdge = edges.find(edge => {
            if (!edge || typeof edge !== 'object') return false
            const target = String(edge.target_node || edge.target || '').trim()
            return target === nodeKey
          })

          const dataMapping = node.data_mapping || {}
          return createSubgraphTemplate({
            node_key: nodeKey || 'scene:{{ index }}',
            node_type: this.normalizeNodeType(node.node_type),
            title: String(dataMapping.label || '').trim(),
            text: String(dataMapping.text || '').trim(),
            prompt: String(dataMapping.prompt || '').trim(),
            connect_source: incomingEdge ? String(incomingEdge.source_node || incomingEdge.source || '').trim() : '',
            rawNode: { ...node },
            rawEdge: incomingEdge ? { ...incomingEdge } : {}
          })
        })
    },

    buildGraphFromTemplateForm() {
      const templates = this.subgraphTemplates
        .map(template => ({
          ...template,
          node_key: String(template.node_key || '').trim(),
          node_type: String(template.node_type || '').trim(),
          title: String(template.title || '').trim(),
          text: String(template.text || '').trim(),
          prompt: String(template.prompt || '').trim(),
          connect_source: String(template.connect_source || '').trim()
        }))
        .filter(template => template.node_key || template.node_type || template.title || template.text || template.prompt)

      for (const template of templates) {
        if (!template.node_key) {
          this.$message?.error('请填写子节点标识')
          return null
        }
        if (!template.node_type) {
          this.$message?.error('请填写节点类型')
          return null
        }
      }

      const nodes = templates.map((template, index) => {
        const rawNode = template.rawNode && typeof template.rawNode === 'object' ? template.rawNode : {}
        const node = {
          ...rawNode,
          node_key: template.node_key,
          node_type: template.node_type,
          title: template.title || template.node_key,
          data_mapping: {}
        }

        if (template.title) {
          node.data_mapping.label = template.title
        }
        if (template.text) {
          node.data_mapping.text = template.text
        }
        if (template.prompt) {
          node.data_mapping.prompt = template.prompt
        }

        if (!node.position_x) {
          node.position_x = 480 + (index % 2) * 480
        }
        if (!node.position_y) {
          node.position_y = Math.floor(index / 2) * 320
        }
        return node
      })

      const edges = templates
        .filter(template => template.connect_source)
        .map(template => {
          const rawEdge = template.rawEdge && typeof template.rawEdge === 'object' ? template.rawEdge : {}
          return {
            ...rawEdge,
            edge_key: rawEdge.edge_key || `edge:${template.connect_source}:${template.node_key}`,
            source_node: template.connect_source,
            target_node: template.node_key
          }
        })

      return { nodes, edges }
    },

    addSubgraphTemplate() {
      this.subgraphTemplates.push(createSubgraphTemplate({
        node_key: `scene_${this.subgraphTemplates.length + 1}:{{ index }}`
      }))
    },

    removeSubgraphTemplate(index) {
      this.subgraphTemplates.splice(index, 1)
      const validSources = new Set(['$parent', ...this.subgraphTemplates.map(template => String(template.node_key || '').trim()).filter(Boolean)])
      this.subgraphTemplates.forEach(template => {
        if (template.connect_source && !validSources.has(template.connect_source)) {
          template.connect_source = ''
          template.rawEdge = {}
        }
      })
    },

    getConnectionSourceOptions(currentIndex) {
      return this.subgraphTemplates
        .map((template, index) => ({
          value: String(template.node_key || '').trim(),
          label: `子节点 ${index + 1}: ${String(template.node_key || '').trim() || '未命名'}`
        }))
        .filter((option, index) => index !== currentIndex && option.value)
    },

    isAllowedNodeType(nodeType) {
      const value = String(nodeType || '').trim()
      return this.nodeTypeOptions.some(option => option.value === value)
    },

    normalizeNodeType(nodeType) {
      const value = String(nodeType || '').trim()
      return this.isAllowedNodeType(value) ? value : 'rewrite'
    },

    async handleSubmit() {
      this.submitting = true
      try {
        const graph = this.buildGraphFromTemplateForm()
        if (!graph) {
          return
        }

        const schemaConfig = {
          ...this.schemaConfig,
          materialization: {
            ...(this.schemaConfig.materialization || {}),
            graph
          }
        }
        const payload = {
          ...this.formData,
          schema_config: schemaConfig
        }

        if (this.isEdit) {
          await workflowNodeSchemaApi.update(this.$route.params.id, payload)
          this.$message?.success('节点结构定义已更新')
        } else {
          await workflowNodeSchemaApi.create(payload)
          this.$message?.success('节点结构定义已创建')
        }

        this.$router.push({ name: 'NodeSchemaManager' })
      } catch (error) {
        console.error('保存节点结构定义失败:', error)
        const msg = error?.response?.data?.detail || error?.message || '保存失败'
        this.$message?.error(msg)
      } finally {
        this.submitting = false
      }
    },

    handleCancel() {
      this.$router.push({ name: 'NodeSchemaManager' })
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

.form-layout {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.panel-card {
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.7) 0%, rgba(14, 165, 233, 0.7) 100%) 0 0 / 0 3px no-repeat,
    rgba(255, 255, 255, 0.92);
  border-radius: 18px;
  padding: 1.35rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
  transition: all 0.3s ease;
}

.layout-shell.theme-dark .panel-card {
  background: linear-gradient(90deg, rgba(94, 234, 212, 0.5) 0%, rgba(56, 189, 248, 0.5) 100%) 0 0 / 0 3px no-repeat,
    rgba(15, 23, 42, 0.92);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 16px 32px rgba(2, 6, 23, 0.55);
}

.panel-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
  border-color: rgba(148, 163, 184, 0.35);
  background-size: 100% 3px, auto;
}

.layout-shell.theme-dark .panel-card:hover {
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.6);
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

.form-grid-spaced {
  margin-top: 1rem;
}

.subgraph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.toolbar-copy {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.compact-action {
  flex: 0 0 auto;
  padding: 0.6rem 1rem;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.template-item {
  padding: 1rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(248, 250, 252, 0.82);
}

.layout-shell.theme-dark .template-item {
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.72);
}

.template-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  color: #0f172a;
}

.layout-shell.theme-dark .template-item-header {
  color: #e2e8f0;
}

.text-action {
  border: 0;
  background: transparent;
  color: #0f766e;
  font-size: 0.88rem;
  cursor: pointer;
  padding: 0.25rem 0.35rem;
}

.layout-shell.theme-dark .text-action {
  color: #5eead4;
}

.text-action:hover {
  text-decoration: underline;
}

.empty-template {
  padding: 1rem;
  border-radius: 14px;
  border: 1px dashed rgba(148, 163, 184, 0.32);
  color: #64748b;
  background: rgba(248, 250, 252, 0.7);
}

.layout-shell.theme-dark .empty-template {
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.72);
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

.field-label em {
  font-style: normal;
  color: #ef4444;
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
  font-family: inherit;
  font-size: 0.95rem;
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

.field-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.field-textarea {
  resize: vertical;
  min-height: 80px;
}

.field-textarea-lg {
  min-height: 180px;
}

.field-textarea-xl {
  min-height: 320px;
}

.code-textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  line-height: 1.5;
  white-space: pre;
}

.field-hint {
  font-size: 0.78rem;
  color: #94a3b8;
}

.toggle-card {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.layout-shell.theme-dark .toggle-card {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.2);
}

.toggle-track {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toggle-track input[type="checkbox"] {
  width: 2.5rem;
  height: 1.4rem;
  border-radius: 999px;
  appearance: none;
  background: rgba(148, 163, 184, 0.35);
  cursor: pointer;
  position: relative;
  transition: background 0.2s ease;
}

.toggle-track input[type="checkbox"]::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s ease;
}

.toggle-track input[type="checkbox"]:checked {
  background: rgba(20, 184, 166, 0.7);
}

.toggle-track input[type="checkbox"]:checked::after {
  transform: translateX(1.1rem);
}

.toggle-text {
  font-size: 0.92rem;
  color: #334155;
}

.layout-shell.theme-dark .toggle-text {
  color: #e2e8f0;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  padding-top: 0.5rem;
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

.primary-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.secondary-outline-action {
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
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.9);
  color: #334155;
}

.layout-shell.theme-dark .secondary-outline-action {
  background: rgba(15, 23, 42, 0.9);
  border-color: rgba(148, 163, 184, 0.22);
  color: #e2e8f0;
}

.secondary-outline-action:hover {
  border-color: rgba(20, 184, 166, 0.6);
  box-shadow: 0 12px 24px rgba(20, 184, 166, 0.18);
  transform: translateY(-1px);
}

.secondary-outline-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
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

  .form-grid {
    grid-template-columns: 1fr;
  }

  .subgraph-toolbar {
    flex-direction: column;
  }

  .compact-action {
    width: 100%;
  }

  .form-actions {
    flex-direction: column;
  }
}
</style>

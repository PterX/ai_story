import apiClient from '@/services/apiClient';

export const createDefaultSchemaConfig = () => ({
  output_schema: {
    output_type: 'collection',
    items_path: 'items',
    source_text_path: 'source_text',
    summary_path: 'summary',
  },
  materialization: {
    mode: 'per_item_subgraph',
    graph: {
      nodes: [],
      edges: [],
    },
  },
});

export const workflowNodeSchemaApi = {
  getList(params = {}) {
    return apiClient.get('/workflows/node-schemas/', { params });
  },

  getDetail(id) {
    return apiClient.get(`/workflows/node-schemas/${id}/`);
  },

  create(data) {
    return apiClient.post('/workflows/node-schemas/', data);
  },

  update(id, data) {
    return apiClient.put(`/workflows/node-schemas/${id}/`, data);
  },

  patch(id, data) {
    return apiClient.patch(`/workflows/node-schemas/${id}/`, data);
  },

  delete(id) {
    return apiClient.delete(`/workflows/node-schemas/${id}/`);
  },
};

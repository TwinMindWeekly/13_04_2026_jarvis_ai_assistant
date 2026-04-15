import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const chatAPI = {
  send: (messages, provider, model) =>
    api.post('/chat', { messages, provider, model, stream: false }),
  getProviders: () => api.get('/providers'),
  testProvider: (provider, apiKey) =>
    api.post('/providers/test', { provider, api_key: apiKey || '' }),
}

export const agentAPI = {
  execute: (message, provider, model, conversationId) =>
    api.post('/agent/execute', {
      message,
      provider,
      model,
      conversation_id: conversationId,
    }),
}

export const documentsAPI = {
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => api.get('/documents/'),
  delete: (docId) => api.delete(`/documents/${docId}`),
}

export const graphAPI = {
  getData: (threshold = 0.5, force = false) =>
    api.get('/graph/data', { params: { threshold, force } }),
  getStats: () => api.get('/graph/stats'),
  rebuild: (threshold = 0.5) =>
    api.post('/graph/rebuild', null, { params: { threshold } }),
}

export const usageAPI = {
  getUsage: () => api.get('/usage/'),
}

export default api

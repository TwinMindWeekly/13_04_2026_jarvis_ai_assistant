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
  execute: (message, provider, model, conversationId, language, signal, history) =>
    api.post('/agent/execute', {
      message,
      provider,
      model,
      language: language || 'en',
      conversation_id: conversationId,
      history: history || [],
    }, { signal }),
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
  create: (filename, folder_path = '', content = '') =>
    api.post('/documents/create', { filename, folder_path, content }),
  update: (docId, { filename, folder_path, sort_order } = {}) =>
    api.patch(`/documents/${docId}`, { filename, folder_path, sort_order }),
  reorder: (items) => api.post('/documents/reorder', items),
}

export const graphAPI = {
  getData: (threshold = 0.5, force = false) =>
    api.get('/graph/data', { params: { threshold, force } }),
  getStats: () => api.get('/graph/stats'),
  rebuild: (threshold = 0.5) =>
    api.post('/graph/rebuild', null, { params: { threshold } }),
}

export const vaultAPI = {
  get: (docId) => api.get(`/vault/${docId}`),
  save: (docId, content) => api.put(`/vault/${docId}`, { content }),
}

export const attachmentAPI = {
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/agent/upload-attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const usageAPI = {
  getUsage: () => api.get('/usage/'),
}

export const ttsAPI = {
  speak: (text, voice = '') =>
    api.post('/tts/speak', { text, voice }, { responseType: 'blob' }),
  voices: () => api.get('/tts/voices'),
}

export const filesAPI = {
  reveal: (path) => api.post('/files/reveal', { path }),
}

export default api

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

export const emailAccountsAPI = {
  list: () => api.get('/email-accounts'),
  create: (payload) => api.post('/email-accounts', payload),
  update: (id, payload) => api.patch(`/email-accounts/${id}`, payload),
  remove: (id) => api.delete(`/email-accounts/${id}`),
  test: (id) => api.post(`/email-accounts/${id}/test`),
}

export const profileAPI = {
  get: () => api.get('/profile'),
  update: (payload) => api.put('/profile', payload),
  uploadCV: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/profile/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const jobsAPI = {
  list: (params = {}) => api.get('/jobs', { params }),
  refresh: () => api.post('/jobs/refresh'),
  save: (jobId) => api.post(`/jobs/${jobId}/save`),
  unsave: (jobId) => api.delete(`/jobs/${jobId}/save`),
  savedSearches: () => api.get('/jobs/saved-searches'),
  createSavedSearch: (payload) => api.post('/jobs/saved-searches', payload),
  deleteSavedSearch: (id) => api.delete(`/jobs/saved-searches/${id}`),
}

export const cvsAPI = {
  list: (kind) => api.get('/cvs', { params: kind ? { kind } : {} }),
  get: (id) => api.get(`/cvs/${id}`),
  create: (payload) => api.post('/cvs', payload),
  update: (id, payload) => api.patch(`/cvs/${id}`, payload),
  remove: (id) => api.delete(`/cvs/${id}`),
  upload: (file, kind = 'cv', title = '') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('kind', kind)
    if (title) fd.append('title', title)
    return api.post('/cvs/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  exportPdf: (id) => api.post(`/cvs/${id}/export`),
  downloadUrl: (id) => `/api/cvs/${id}/pdf`,
  previewUrl: (id) => `/api/cvs/${id}/preview.html`,
  tailor: (id, jobId, newTitle) =>
    api.post(`/cvs/${id}/tailor`, { job_id: jobId, new_title: newTitle || null }),
}

export default api

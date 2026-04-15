import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const chatAPI = {
  send: (messages, provider, model) =>
    api.post('/chat', { messages, provider, model, stream: false }),
  getProviders: () => api.get('/providers'),
  testProvider: (provider, apiKey) =>
    api.post('/providers/test', { provider, api_key: apiKey }),
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

export default api

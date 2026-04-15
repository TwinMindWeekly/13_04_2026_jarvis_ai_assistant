import { useState, useCallback, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Bot, User, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { agentAPI } from '../services/api'

/**
 * GraphChatPanel — right sidebar AI chat for querying documents within
 * the graph view. Uses the same /api/agent/execute endpoint (which has
 * rag_search tool) so the agent can search uploaded documents.
 *
 * When the AI response mentions document filenames, those nodes get
 * highlighted on the graph via onHighlightNodes callback.
 */
export default function GraphChatPanel({
  settings,
  graphNodes,
  onHighlightNodes,
  onSelectNode,
}) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const listRef = useRef(null)

  // Auto-scroll to bottom on new messages.
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, isLoading])

  // Find which graph nodes are mentioned in the AI response text.
  const findMentionedNodes = useCallback(
    (text) => {
      if (!text || !graphNodes?.length) return []
      const lower = text.toLowerCase()
      return graphNodes.filter((n) => {
        const name = (n.label || '').toLowerCase()
        return name.length > 2 && lower.includes(name)
      })
    },
    [graphNodes]
  )

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isLoading) return

    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)
    onHighlightNodes([])

    try {
      const { data } = await agentAPI.execute(
        text,
        settings.provider,
        settings.model,
        null
      )
      const assistantMsg = {
        role: 'assistant',
        content: data.response,
        actions: data.actions,
      }
      setMessages((prev) => [...prev, assistantMsg])

      // Highlight mentioned document nodes on the graph.
      const mentioned = findMentionedNodes(data.response)
      if (mentioned.length > 0) {
        onHighlightNodes(mentioned.map((n) => n.id))
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Error'
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${errorMsg}` },
      ])
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, settings, findMentionedNodes, onHighlightNodes])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  // Extract mentioned doc names from a message for clickable chips.
  const mentionedDocsInMsg = useCallback(
    (text) => findMentionedNodes(text),
    [findMentionedNodes]
  )

  return (
    <div className="graph-chat-panel">
      <div className="graph-chat-header">
        <Bot size={18} />
        <span>{t('graph.aiChatTitle', 'Document AI')}</span>
      </div>

      <div className="graph-chat-messages" ref={listRef}>
        {messages.length === 0 && (
          <div className="graph-chat-empty">
            <Bot size={32} style={{ color: '#555', marginBottom: 8 }} />
            <p>{t('graph.aiChatHint', 'Ask JARVIS about your documents. It will search and highlight related nodes on the graph.')}</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`graph-chat-msg graph-chat-msg-${msg.role}`}>
            <div className="graph-chat-msg-icon">
              {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className="graph-chat-msg-body">
              {msg.role === 'assistant' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              ) : (
                <p>{msg.content}</p>
              )}
              {/* Clickable doc chips for mentioned documents */}
              {msg.role === 'assistant' && (() => {
                const docs = mentionedDocsInMsg(msg.content)
                if (docs.length === 0) return null
                return (
                  <div className="graph-chat-doc-chips">
                    {docs.map((n) => (
                      <button
                        key={n.id}
                        className="graph-chat-doc-chip"
                        onClick={() => onSelectNode(n)}
                        title={`Focus on ${n.label}`}
                      >
                        {n.label}
                      </button>
                    ))}
                  </div>
                )
              })()}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="graph-chat-msg graph-chat-msg-assistant">
            <div className="graph-chat-msg-icon"><Bot size={14} /></div>
            <div className="graph-chat-msg-body">
              <Loader2 size={16} className="animate-spin" style={{ color: '#888' }} />
            </div>
          </div>
        )}
      </div>

      <div className="graph-chat-input-bar">
        <input
          type="text"
          placeholder={t('graph.askJarvis', 'Ask JARVIS about documents...')}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          className="graph-chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          aria-label="Send"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}

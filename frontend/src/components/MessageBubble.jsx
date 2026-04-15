import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Zap } from 'lucide-react'

const messageVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] },
  },
}

function StreamingCursor() {
  return (
    <motion.span
      style={{
        display: 'inline-block',
        width: 2,
        height: '1.1em',
        marginLeft: 2,
        borderRadius: 2,
        verticalAlign: 'text-bottom',
        background: 'var(--accent)',
      }}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
    />
  )
}

function UserAvatar() {
  return <div className="avatar-user">U</div>
}

function AssistantAvatar() {
  return (
    <div className="avatar-assistant">
      <Zap size={15} />
    </div>
  )
}

export default function MessageBubble({ message, isStreaming = false }) {
  const isUser = message.role === 'user'
  const actionCount = message.actions?.length ?? 0
  const label = isUser ? 'You' : 'JARVIS'

  return (
    <motion.div
      variants={messageVariants}
      initial="hidden"
      animate="visible"
      className="message-row"
    >
      {/* Inner content — full width with comfortable side padding */}
      <div
        className="w-100 px-4 d-flex gap-3"
      >
        {isUser ? <UserAvatar /> : <AssistantAvatar />}

        <div className="d-flex flex-column gap-1 flex-grow-1" style={{ minWidth: 0 }}>
          <span
            className="fw-semibold"
            style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}
          >
            {label}
          </span>

          {actionCount > 0 && (
            <div className="tool-used-badge">
              <Zap size={11} />
              Used {actionCount} tool{actionCount !== 1 ? 's' : ''}
            </div>
          )}

          {isUser ? (
            <p
              style={{
                margin: 0,
                fontSize: '1rem',
                lineHeight: 1.75,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-words',
                color: 'var(--text-primary)',
              }}
            >
              {message.content}
            </p>
          ) : (
            <div
              className="markdown-content"
              style={{ fontSize: '1rem', lineHeight: 1.75, color: 'var(--text-primary)' }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

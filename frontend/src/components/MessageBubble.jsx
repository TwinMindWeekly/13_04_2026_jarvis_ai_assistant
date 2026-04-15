import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Zap } from 'lucide-react'

const bubbleVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] },
  },
}

function StreamingCursor() {
  return (
    <motion.span
      className="inline-block w-[2px] h-[1.1em] ml-0.5 rounded-sm align-text-bottom"
      style={{ background: 'var(--accent)' }}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
    />
  )
}

export default function MessageBubble({ message, isStreaming = false }) {
  const isUser = message.role === 'user'
  const actionCount = message.actions?.length ?? 0

  return (
    <motion.div
      variants={bubbleVariants}
      initial="hidden"
      animate="visible"
      className={`flex gap-3 w-full ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1"
          style={{
            background: 'rgba(99,102,241,0.15)',
            border: '1px solid rgba(99,102,241,0.35)',
          }}
        >
          <Zap size={13} style={{ color: 'var(--accent)' }} />
        </div>
      )}

      <div className={`flex flex-col gap-1.5 max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
        {actionCount > 0 && (
          <div
            className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium"
            style={{
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.25)',
              color: 'var(--accent-hover)',
            }}
          >
            <Zap size={10} />
            Used {actionCount} tool{actionCount !== 1 ? 's' : ''}
          </div>
        )}

        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? 'rounded-tr-sm'
              : 'rounded-tl-sm'
          }`}
          style={
            isUser
              ? {
                  background: 'var(--accent)',
                  color: '#fff',
                  boxShadow: '0 4px 24px rgba(99,102,241,0.3)',
                }
              : {
                  background: 'var(--glass-bg)',
                  border: '1px solid var(--glass-border)',
                  backdropFilter: 'blur(12px)',
                  WebkitBackdropFilter: 'blur(12px)',
                  color: 'var(--text-primary)',
                  boxShadow: 'var(--glass-shadow)',
                }
          }
        >
          {isUser ? (
            <span className="whitespace-pre-wrap break-words">{message.content}</span>
          ) : (
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
          )}
        </div>
      </div>

      {isUser && (
        <div
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 text-xs font-bold"
          style={{
            background: 'rgba(148,163,184,0.1)',
            border: '1px solid rgba(148,163,184,0.2)',
            color: 'var(--text-secondary)',
          }}
        >
          U
        </div>
      )}
    </motion.div>
  )
}

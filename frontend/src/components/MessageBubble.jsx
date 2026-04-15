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
      className="inline-block w-[2px] h-[1.1em] ml-0.5 rounded-sm align-text-bottom"
      style={{ background: 'var(--accent)' }}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
    />
  )
}

function UserAvatar() {
  return (
    <div
      className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold"
      style={{
        background: '#565869',
        color: '#ececec',
      }}
    >
      U
    </div>
  )
}

function AssistantAvatar() {
  return (
    <div
      className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
      style={{
        background: 'var(--accent)',
        color: '#fff',
      }}
    >
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
      className="flex gap-4 w-full py-5 px-4"
      style={{
        borderBottom: '1px solid var(--border-light)',
      }}
    >
      {isUser ? <UserAvatar /> : <AssistantAvatar />}

      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <span
          className="text-sm font-semibold"
          style={{ color: 'var(--text-secondary)' }}
        >
          {label}
        </span>

        {actionCount > 0 && (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium w-fit mb-1"
            style={{
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.25)',
              color: 'var(--accent-hover)',
            }}
          >
            <Zap size={11} />
            Used {actionCount} tool{actionCount !== 1 ? 's' : ''}
          </div>
        )}

        {isUser ? (
          <p
            className="text-base leading-7 whitespace-pre-wrap break-words"
            style={{ color: 'var(--text-primary)' }}
          >
            {message.content}
          </p>
        ) : (
          <div
            className="markdown-content text-base leading-7"
            style={{ color: 'var(--text-primary)' }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {isStreaming && <StreamingCursor />}
          </div>
        )}
      </div>
    </motion.div>
  )
}

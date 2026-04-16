import { motion, AnimatePresence } from 'framer-motion'

// Props: status = 'idle' | 'loading' | 'speaking' | 'error'
export default function JarvisOrb({ status = 'idle' }) {
  const isLoading = status === 'loading'
  const isSpeaking = status === 'speaking'
  const isError = status === 'error'

  // Core color per state
  const coreColor = isError
    ? '#ef4444'
    : isSpeaking
      ? '#34d399'
      : '#6366f1'

  const glowColor = isError
    ? 'rgba(239,68,68,0.55)'
    : isSpeaking
      ? 'rgba(52,211,153,0.45)'
      : 'rgba(99,102,241,0.5)'

  const ringColor = isError
    ? 'rgba(239,68,68,0.7)'
    : isSpeaking
      ? 'rgba(52,211,153,0.6)'
      : 'rgba(129,140,248,0.6)'

  // Outer ring spin speed
  const outerDuration = isLoading ? 1.2 : 4
  const midDuration = isLoading ? 0.9 : 6
  const innerDuration = isLoading ? 1.6 : 8

  // Breathing scale for idle
  const breatheAnim = {
    scale: isLoading ? [1, 1.08, 1] : [1, 1.04, 1],
    transition: {
      duration: isLoading ? 0.9 : 2.8,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  }

  // EQ bar heights for speaking state (5 bars)
  const eqBars = [0.45, 0.75, 1, 0.65, 0.35]

  return (
    <div className="jarvis-orb-wrapper" aria-label={`JARVIS status: ${status}`}>
      {/* Orb container */}
      <div className="jarvis-orb">
        {/* Ambient glow layer — blurs outward */}
        <motion.div
          className="orb-ambient"
          style={{ background: glowColor }}
          animate={breatheAnim}
        />

        {/* Outer dashed ring — slowest */}
        <motion.div
          className="orb-ring orb-ring--outer"
          style={{ borderColor: ringColor }}
          animate={{ rotate: 360 }}
          transition={{
            duration: outerDuration,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* Mid ring — counter-rotate */}
        <motion.div
          className="orb-ring orb-ring--mid"
          style={{ borderColor: ringColor }}
          animate={{ rotate: -360 }}
          transition={{
            duration: midDuration,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* Inner ring — fastest */}
        <motion.div
          className="orb-ring orb-ring--inner"
          style={{ borderColor: ringColor }}
          animate={{ rotate: 360 }}
          transition={{
            duration: innerDuration,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* Core glow sphere */}
        <motion.div
          className="orb-core"
          style={{
            background: `radial-gradient(circle at 38% 35%, ${isError ? '#fca5a5' : isSpeaking ? '#6ee7b7' : '#a5b4fc'} 0%, ${coreColor} 45%, ${isError ? '#7f1d1d' : isSpeaking ? '#065f46' : '#312e81'} 100%)`,
            boxShadow: `0 0 12px 4px ${glowColor}, inset 0 0 8px rgba(255,255,255,0.15)`,
          }}
          animate={breatheAnim}
        >
          {/* Specular highlight dot */}
          <div className="orb-specular" />

          {/* Loading arc — shows only when loading */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                key="loading-arc"
                className="orb-loading-arc"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ duration: 0.25 }}
              />
            )}
          </AnimatePresence>
        </motion.div>

        {/* EQ bars — visible only when speaking */}
        <AnimatePresence>
          {isSpeaking && (
            <motion.div
              key="eq-bars"
              className="orb-eq"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {eqBars.map((baseH, i) => (
                <motion.span
                  key={i}
                  className="orb-eq-bar"
                  style={{ background: coreColor }}
                  animate={{
                    scaleY: [baseH, 1, baseH * 0.6, 0.9, baseH],
                  }}
                  transition={{
                    duration: 0.6 + i * 0.07,
                    repeat: Infinity,
                    ease: 'easeInOut',
                    delay: i * 0.08,
                  }}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Label below orb */}
      <AnimatePresence mode="wait">
        <motion.span
          key={status}
          className="jarvis-orb-label"
          initial={{ opacity: 0, y: 3 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -3 }}
          transition={{ duration: 0.2 }}
          style={{ color: isError ? '#ef4444' : 'var(--text-muted)' }}
        >
          {isLoading
            ? 'Thinking...'
            : isSpeaking
              ? 'Speaking'
              : isError
                ? 'Error'
                : 'JARVIS'}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

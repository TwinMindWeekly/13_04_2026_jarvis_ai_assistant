import { motion } from 'framer-motion'
import { Mic, MicOff, Volume2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/**
 * VoiceButton — Mic toggle with wave animation when listening.
 *
 * Props:
 *   isListening  — whether STT is active
 *   isSpeaking   — whether TTS is playing
 *   supported    — whether STT is supported in this browser
 *   onToggle     — callback to start/stop listening
 *   onStopTTS    — callback to stop TTS playback
 */
export default function VoiceButton({
  isListening = false,
  isSpeaking = false,
  supported = true,
  onToggle,
  onStopTTS,
}) {
  const { t } = useTranslation()

  if (!supported) return null

  // If TTS is speaking, show stop button
  if (isSpeaking) {
    return (
      <motion.button
        onClick={onStopTTS}
        className="voice-btn speaking"
        whileTap={{ scale: 0.9 }}
        aria-label="Stop speaking"
        title="Stop speaking"
      >
        <Volume2 size={18} />
        {/* Pulse rings while speaking */}
        <span className="voice-pulse-ring" />
        <span className="voice-pulse-ring delay" />
      </motion.button>
    )
  }

  return (
    <motion.button
      onClick={onToggle}
      className={`voice-btn ${isListening ? 'listening' : ''}`}
      whileTap={{ scale: 0.9 }}
      aria-label={isListening ? 'Stop listening' : 'Start voice input'}
      title={isListening ? 'Stop listening' : 'Voice input'}
    >
      {isListening ? <MicOff size={18} /> : <Mic size={18} />}
      {isListening && (
        <>
          <span className="voice-pulse-ring" />
          <span className="voice-pulse-ring delay" />
        </>
      )}
    </motion.button>
  )
}

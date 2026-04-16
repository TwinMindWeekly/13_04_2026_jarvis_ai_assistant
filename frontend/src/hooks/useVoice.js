import { useState, useRef, useCallback, useEffect } from 'react'
import { ttsAPI } from '../services/api'

/**
 * useVoice — Speech-to-Text (Web Speech API) + Text-to-Speech (Edge TTS server)
 *
 * STT: Listens via microphone, returns transcript, auto-sends on silence.
 * TTS: Sends text to backend Edge TTS → receives MP3 → plays via <audio>.
 *      Edge TTS voices handle Vietnamese + English naturally in one voice.
 *
 * Browser support: Chrome, Edge (full), Safari (partial), Firefox (no STT).
 */

const SpeechRecognition =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

export function useVoice({ language = 'en-US', onTranscript, enabled = true } = {}) {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [sttSupported] = useState(() => !!SpeechRecognition)
  const [speakingCharIndex, setSpeakingCharIndex] = useState(-1)

  const recognitionRef = useRef(null)
  const audioRef = useRef(null)
  const abortRef = useRef(null)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // --- STT: Start listening ---
  const startListening = useCallback(() => {
    if (!sttSupported || !enabled || isListening) return

    const recognition = new SpeechRecognition()
    recognition.lang = language
    recognition.interimResults = true
    recognition.continuous = false
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setIsListening(true)
      setTranscript('')
    }

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''

      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalText += result[0].transcript
        } else {
          interimText += result[0].transcript
        }
      }

      setTranscript(finalText || interimText)

      if (finalText && onTranscriptRef.current) {
        onTranscriptRef.current(finalText.trim())
        setTranscript('')
      }
    }

    recognition.onerror = (event) => {
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setIsListening(false)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [sttSupported, enabled, isListening, language])

  // --- STT: Stop listening ---
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      const ref = recognitionRef.current
      recognitionRef.current = null
      ref.stop()
    }
  }, [])

  // --- STT: Toggle ---
  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }, [isListening, startListening, stopListening])

  // --- TTS: Speak text via Edge TTS server ---
  // Sends text to POST /api/tts/speak → receives MP3 blob → plays via Audio element.
  // Edge TTS vi-VN-HoaiMyNeural handles Vietnamese + English terms naturally.
  const speak = useCallback(
    async (text, _voiceName, { append = false } = {}) => {
      if (!enabled || !text) return

      // Stop any current playback
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      if (abortRef.current) {
        abortRef.current.abort()
      }

      const langCode = language.startsWith('vi') ? 'vi' : 'en'
      setIsSpeaking(true)
      setSpeakingCharIndex(0)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        const { data: blob } = await ttsAPI.speak(text, langCode)

        if (controller.signal.aborted) return

        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio

        // Estimate reading progress based on audio time
        const totalChars = text.length
        audio.ontimeupdate = () => {
          if (audio.duration > 0) {
            const progress = audio.currentTime / audio.duration
            setSpeakingCharIndex(Math.floor(progress * totalChars))
          }
        }

        audio.onended = () => {
          setIsSpeaking(false)
          setSpeakingCharIndex(-1)
          URL.revokeObjectURL(url)
          audioRef.current = null
        }

        audio.onerror = () => {
          setIsSpeaking(false)
          setSpeakingCharIndex(-1)
          URL.revokeObjectURL(url)
          audioRef.current = null
        }

        audio.play()
      } catch (err) {
        if (!controller.signal.aborted) {
          console.error('[TTS] Edge TTS failed:', err)
          setIsSpeaking(false)
          setSpeakingCharIndex(-1)
        }
      }
    },
    [enabled, language]
  )

  // --- TTS: Stop speaking ---
  const stopSpeaking = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setIsSpeaking(false)
    setSpeakingCharIndex(-1)
  }, [])

  return {
    // STT
    isListening,
    transcript,
    startListening,
    stopListening,
    toggleListening,
    sttSupported,

    // TTS
    isSpeaking,
    speak,
    stopSpeaking,
    ttsSupported: true, // Edge TTS is always available (server-side)
    speakingCharIndex,
    voiceMissing: false, // Edge TTS always has Vietnamese voice
  }
}

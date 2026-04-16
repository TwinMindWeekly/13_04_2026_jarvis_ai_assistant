import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useVoice — Speech-to-Text (Web Speech API) + Text-to-Speech (SpeechSynthesis)
 *
 * STT: Listens via microphone, returns transcript, auto-sends on silence.
 * TTS: Reads text aloud using browser SpeechSynthesis.
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
  const [ttsSupported] = useState(() => typeof window !== 'undefined' && 'speechSynthesis' in window)
  const [availableVoices, setAvailableVoices] = useState([])
  // Voice-synced text reveal: how many chars of the current speech have been spoken
  const [revealedText, setRevealedText] = useState('')
  const fullSpeechTextRef = useRef('')
  const revealOffsetRef = useRef(0)

  const recognitionRef = useRef(null)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  // Load available TTS voices
  useEffect(() => {
    if (!ttsSupported) return

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      if (voices.length > 0) {
        setAvailableVoices(voices)
      }
    }

    loadVoices()
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', loadVoices)
    }
  }, [ttsSupported])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
      if (ttsSupported) {
        window.speechSynthesis.cancel()
      }
    }
  }, [ttsSupported])

  // --- STT: Start listening ---
  const startListening = useCallback(() => {
    if (!sttSupported || !enabled || isListening) return

    const recognition = new SpeechRecognition()
    recognition.lang = language
    recognition.interimResults = true
    // continuous=false: stop after one final result so we don't echo-loop
    // when TTS plays the response back through the speakers
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

      // Auto-send when we get a final result, then clear transcript
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

    // continuous=false: when recognition ends naturally, just stop.
    // User must click mic again to record next message — prevents TTS echo loop.
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
      recognitionRef.current = null  // signal onend: user stopped intentionally
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

  // --- TTS: Speak text with word-level reveal ---
  // append=true: queue utterance without cancelling (streaming TTS)
  // append=false: cancel current speech, start fresh (REST TTS)
  const speak = useCallback(
    (text, voiceName, { append = false } = {}) => {
      if (!ttsSupported || !enabled || !text) return

      if (!append) {
        window.speechSynthesis.cancel()
        fullSpeechTextRef.current = text
        revealOffsetRef.current = 0
        setRevealedText('\u200b') // truthy placeholder — prevents full text flash
      } else {
        fullSpeechTextRef.current += text
      }

      const currentOffset = revealOffsetRef.current

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = language
      utterance.rate = 1.0
      utterance.pitch = 1.0

      if (voiceName) {
        const v = availableVoices.find((voice) => voice.name === voiceName)
        if (v) utterance.voice = v
      }

      utterance.onstart = () => setIsSpeaking(true)

      // Word boundary event — reveal text up to the word being spoken
      utterance.onboundary = (event) => {
        if (event.name === 'word') {
          const revealEnd = currentOffset + event.charIndex + event.charLength
          setRevealedText(fullSpeechTextRef.current.slice(0, revealEnd))
        }
      }

      utterance.onend = () => {
        // Reveal all text for this utterance
        revealOffsetRef.current = currentOffset + text.length
        setRevealedText(fullSpeechTextRef.current.slice(0, revealOffsetRef.current))
        if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
          setIsSpeaking(false)
          setRevealedText('') // Clear — full text is in messages now
        }
      }
      utterance.onerror = () => {
        setIsSpeaking(false)
        setRevealedText('')
      }

      window.speechSynthesis.speak(utterance)
    },
    [ttsSupported, enabled, language, availableVoices]
  )

  // --- TTS: Stop speaking ---
  const stopSpeaking = useCallback(() => {
    if (ttsSupported) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      setRevealedText('')
      fullSpeechTextRef.current = ''
      revealOffsetRef.current = 0
    }
  }, [ttsSupported])

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
    ttsSupported,
    availableVoices,
    revealedText,
  }
}

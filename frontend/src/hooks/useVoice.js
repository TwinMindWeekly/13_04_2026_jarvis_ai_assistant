import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useVoice — Speech-to-Text (Web Speech API) + Text-to-Speech (VieNeu backend)
 *
 * STT: Listens via microphone, returns transcript, auto-sends on silence.
 * TTS: Prefetch pipeline — all fetch requests fire immediately when speak()
 *       is called, audio plays sequentially as blobs arrive. Server processes
 *       them in order (single-thread executor), frontend plays in queue order.
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
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  // TTS playback state
  const audioRef = useRef(null)
  const queueRef = useRef([])         // [{text, offset, blobPromise}]
  const fullTextRef = useRef('')
  const processingRef = useRef(false)
  const generationRef = useRef(0)     // cancel token
  const controllersRef = useRef([])   // AbortControllers for in-flight fetches

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
      generationRef.current++
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      controllersRef.current.forEach((c) => c.abort())
      controllersRef.current = []
    }
  }, [])

  // ── Playback loop — plays pre-fetched audio blobs in queue order ──
  const processQueue = useCallback(async () => {
    if (processingRef.current) return
    processingRef.current = true
    const gen = generationRef.current

    while (queueRef.current.length > 0 && generationRef.current === gen) {
      const { text, offset, blobPromise } = queueRef.current.shift()
      setSpeakingCharIndex(offset)

      try {
        // Wait for the pre-fired fetch to resolve
        const blob = await blobPromise
        if (generationRef.current !== gen || !blob) continue

        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio

        await new Promise((resolve) => {
          const done = () => { URL.revokeObjectURL(url); resolve() }
          audio.ontimeupdate = () => {
            if (audio.duration > 0 && generationRef.current === gen) {
              const progress = audio.currentTime / audio.duration
              setSpeakingCharIndex(offset + Math.floor(progress * text.length))
            }
          }
          audio.onended = done
          audio.onerror = done
          audio.onpause = done
          audio.play().catch(done)
        })

        if (generationRef.current === gen) {
          setSpeakingCharIndex(offset + text.length)
        }
      } catch {
        // fetch aborted or failed — skip to next
      }
    }

    if (generationRef.current === gen) {
      processingRef.current = false
      setIsSpeaking(false)
      setSpeakingCharIndex(-1)
      fullTextRef.current = ''
      controllersRef.current = []
    }
  }, [])

  /** Fire a fetch for TTS and return the blob promise (non-blocking). */
  const _startFetch = useCallback((text, voiceId) => {
    const controller = new AbortController()
    controllersRef.current.push(controller)

    const blobPromise = fetch('/api/tts/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice: voiceId }),
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.blob() : null))
      .catch(() => null)

    return blobPromise
  }, [])

  // ── STT ──
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

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      const ref = recognitionRef.current
      recognitionRef.current = null
      ref.stop()
    }
  }, [])

  const toggleListening = useCallback(() => {
    if (isListening) stopListening()
    else startListening()
  }, [isListening, startListening, stopListening])

  // ── TTS: Speak — fires fetch immediately, queues for sequential playback ──
  const speak = useCallback(
    (text, voiceName, { append = false } = {}) => {
      if (!enabled || !text) return

      const voiceId = voiceName || ''

      if (!append) {
        // Cancel everything
        generationRef.current++
        if (audioRef.current) {
          audioRef.current.pause()
          audioRef.current = null
        }
        controllersRef.current.forEach((c) => c.abort())
        controllersRef.current = []
        queueRef.current = []
        fullTextRef.current = text
        processingRef.current = false

        const blobPromise = _startFetch(text, voiceId)
        queueRef.current.push({ text, offset: 0, blobPromise })
        setSpeakingCharIndex(0)
        setIsSpeaking(true)
        processQueue()
      } else {
        fullTextRef.current += text
        const offset = fullTextRef.current.length - text.length

        // Fire fetch immediately — don't wait for earlier items to finish
        const blobPromise = _startFetch(text, voiceId)
        queueRef.current.push({ text, offset, blobPromise })

        if (!processingRef.current) {
          setIsSpeaking(true)
          processQueue()
        }
      }
    },
    [enabled, processQueue, _startFetch],
  )

  const stopSpeaking = useCallback(() => {
    generationRef.current++
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    controllersRef.current.forEach((c) => c.abort())
    controllersRef.current = []
    queueRef.current = []
    processingRef.current = false
    setIsSpeaking(false)
    setSpeakingCharIndex(-1)
    fullTextRef.current = ''
  }, [])

  return {
    isListening, transcript, startListening, stopListening, toggleListening, sttSupported,
    isSpeaking, speak, stopSpeaking,
    ttsSupported: true,
    availableVoices: [],
    speakingCharIndex,
    voiceMissing: false,
  }
}

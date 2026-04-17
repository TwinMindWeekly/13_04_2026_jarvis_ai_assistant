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
  // Index of the markdown paragraph currently being spoken (-1 when idle).
  // Indexing against markdown source — not stripped text — so highlight aligns with rendered paragraphs.
  const [speakingParagraphIndex, setSpeakingParagraphIndex] = useState(-1)

  const recognitionRef = useRef(null)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  // TTS playback state
  const audioRef = useRef(null)
  const queueRef = useRef([])         // [{text, paragraphIndex, blobPromise}]
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
      const { paragraphIndex, blobPromise } = queueRef.current.shift()
      setSpeakingParagraphIndex(paragraphIndex)

      try {
        // Wait for the pre-fired fetch to resolve
        const blob = await blobPromise
        if (generationRef.current !== gen || !blob) continue

        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio

        await new Promise((resolve) => {
          const done = () => { URL.revokeObjectURL(url); resolve() }
          audio.onended = done
          audio.onerror = done
          audio.onpause = done
          audio.play().catch(done)
        })
      } catch {
        // fetch aborted or failed — skip to next
      }
    }

    if (generationRef.current === gen) {
      processingRef.current = false
      setIsSpeaking(false)
      setSpeakingParagraphIndex(-1)
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
  // `paragraphIndex`: index of the markdown paragraph this chunk represents,
  // so UI can highlight the correct rendered paragraph regardless of markdown stripping.
  const speak = useCallback(
    (text, voiceName, { append = false, paragraphIndex = 0 } = {}) => {
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
        processingRef.current = false

        const blobPromise = _startFetch(text, voiceId)
        queueRef.current.push({ text, paragraphIndex, blobPromise })
        setSpeakingParagraphIndex(paragraphIndex)
        setIsSpeaking(true)
        processQueue()
      } else {
        // Fire fetch immediately — don't wait for earlier items to finish
        const blobPromise = _startFetch(text, voiceId)
        queueRef.current.push({ text, paragraphIndex, blobPromise })

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
    setSpeakingParagraphIndex(-1)
  }, [])

  return {
    isListening, transcript, startListening, stopListening, toggleListening, sttSupported,
    isSpeaking, speak, stopSpeaking,
    ttsSupported: true,
    availableVoices: [],
    speakingParagraphIndex,
    voiceMissing: false,
  }
}

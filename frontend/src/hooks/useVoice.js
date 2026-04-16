import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useVoice — Speech-to-Text (Web Speech API) + Text-to-Speech (SpeechSynthesis)
 *
 * STT: Listens via microphone, returns transcript, auto-sends on silence.
 * TTS: Reads text aloud using browser SpeechSynthesis with multilingual
 *       voice switching (Vietnamese / English) and paragraph-level tracking.
 *
 * Browser support: Chrome, Edge (full), Safari (partial), Firefox (no STT).
 */

const SpeechRecognition =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

// Vietnamese diacritical characters for language detection
const _VI_CHARS = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]/

/**
 * Split text into language segments (Vietnamese / English).
 * Short segments (< 3 words) merge into neighbors to reduce choppiness.
 * Concatenation of all segment texts equals the original text.
 */
function _splitByLanguage(text) {
  const parts = text.match(/\S+\s*/g)
  if (!parts) return [{ text, lang: 'en' }]

  const raw = []
  let curLang = null, curText = '', curWords = 0
  for (const part of parts) {
    const lang = _VI_CHARS.test(part) ? 'vi' : 'en'
    if (curLang === null || lang === curLang) {
      curLang = lang; curText += part; curWords++
    } else {
      raw.push({ text: curText, lang: curLang, words: curWords })
      curLang = lang; curText = part; curWords = 1
    }
  }
  if (curText) raw.push({ text: curText, lang: curLang || 'en', words: curWords })
  if (raw.length <= 1) return raw

  // Merge short segments (< 3 words) into previous to reduce voice-switching choppiness
  const merged = [raw[0]]
  for (let i = 1; i < raw.length; i++) {
    if (raw[i].words < 3) {
      const prev = merged[merged.length - 1]
      prev.text += raw[i].text
      prev.words += raw[i].words
    } else {
      merged.push(raw[i])
    }
  }
  if (merged.length > 1 && merged[0].words < 3) {
    merged[1].text = merged[0].text + merged[1].text
    merged[1].words += merged[0].words
    merged.shift()
  }
  return merged
}

/** Find the best available voice for a language code. */
function _findVoiceForLang(langCode, voices) {
  const prefix = langCode.slice(0, 2).toLowerCase()
  const matching = voices.filter((v) => v.lang.toLowerCase().startsWith(prefix))
  return matching.find((v) => v.localService) || matching[0] || null
}

export function useVoice({ language = 'en-US', onTranscript, enabled = true } = {}) {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [sttSupported] = useState(() => !!SpeechRecognition)
  const [ttsSupported] = useState(() => typeof window !== 'undefined' && 'speechSynthesis' in window)
  const [availableVoices, setAvailableVoices] = useState([])
  // True when no voice matches the current language (e.g. Vietnamese voice not installed)
  const [voiceMissing, setVoiceMissing] = useState(false)
  // Speaking position: character index in the full queued text that TTS has reached
  const [speakingCharIndex, setSpeakingCharIndex] = useState(-1)
  const fullSpeechTextRef = useRef('')

  const recognitionRef = useRef(null)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript

  // Load available TTS voices and check if current language is supported
  useEffect(() => {
    if (!ttsSupported) return

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      if (voices.length > 0) {
        setAvailableVoices(voices)
        const prefix = language.slice(0, 2).toLowerCase()
        const hasMatch = voices.some((v) => v.lang.toLowerCase().startsWith(prefix))
        setVoiceMissing(!hasMatch)
      }
    }

    loadVoices()
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', loadVoices)
    }
  }, [ttsSupported, language])

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

  // --- TTS: Speak text ---
  // Uses the hook's `language` prop to select voice (matches user's language setting).
  // Text is shown in full immediately; TTS speaks in the background.
  // speakingCharIndex tracks the approximate reading position for UI highlighting.
  const speak = useCallback(
    (text, voiceName, { append = false } = {}) => {
      if (!ttsSupported || !enabled || !text) return

      if (!append) {
        window.speechSynthesis.cancel()
        fullSpeechTextRef.current = text
        setSpeakingCharIndex(0)
      } else {
        fullSpeechTextRef.current += text
      }

      const utteranceOffset = fullSpeechTextRef.current.length - text.length

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = language
      utterance.rate = 1.0
      utterance.pitch = 1.0

      // Pick voice: always get fresh list (cached list may be empty on first call)
      const voices = availableVoices.length > 0 ? availableVoices : window.speechSynthesis.getVoices()
      const langPrefix = language.slice(0, 2).toLowerCase()
      let selectedVoice = null
      if (voiceName) {
        const v = voices.find((av) => av.name === voiceName)
        if (v && v.lang.toLowerCase().startsWith(langPrefix)) selectedVoice = v
      }
      if (!selectedVoice) selectedVoice = _findVoiceForLang(language, voices)
      if (selectedVoice) {
        utterance.voice = selectedVoice
      } else {
        // Debug: log available voices so we can diagnose
        console.warn('[TTS] No voice found for', language, '— available:', voices.map((v) => `${v.name} (${v.lang})`))
      }

      utterance.onstart = () => {
        setIsSpeaking(true)
        setSpeakingCharIndex(utteranceOffset)
      }

      utterance.onboundary = (event) => {
        if (event.name === 'word') {
          setSpeakingCharIndex(utteranceOffset + event.charIndex + event.charLength)
        }
      }

      utterance.onend = () => {
        setSpeakingCharIndex(utteranceOffset + text.length)
        if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
          setIsSpeaking(false)
          setSpeakingCharIndex(-1)
          fullSpeechTextRef.current = ''
        }
      }

      utterance.onerror = () => {
        setIsSpeaking(false)
        setSpeakingCharIndex(-1)
        fullSpeechTextRef.current = ''
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
      setSpeakingCharIndex(-1)
      fullSpeechTextRef.current = ''
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
    speakingCharIndex,
    voiceMissing,
  }
}

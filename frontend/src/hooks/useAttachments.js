import { useState, useCallback } from 'react'
import { attachmentAPI } from '../services/api'

const MAX_ATTACHMENTS = 3
const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5 MB

export function useAttachments() {
  const [attachments, setAttachments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)

  const addFile = useCallback(async (file) => {
    setUploadError(null)

    if (attachments.length >= MAX_ATTACHMENTS) {
      setUploadError(`Maximum ${MAX_ATTACHMENTS} files per message.`)
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      setUploadError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 5 MB.`)
      return
    }

    setUploading(true)
    try {
      const { data } = await attachmentAPI.upload(file)
      setAttachments((prev) => [
        ...prev,
        {
          filename: data.filename,
          content: data.content,
          charCount: data.char_count,
          truncated: data.truncated,
        },
      ])
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Upload failed'
      setUploadError(detail)
    } finally {
      setUploading(false)
    }
  }, [attachments.length])

  const removeAttachment = useCallback((index) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
    setUploadError(null)
  }, [])

  const clearAttachments = useCallback(() => {
    setAttachments([])
    setUploadError(null)
  }, [])

  const serializeForPrompt = useCallback(() => {
    if (attachments.length === 0) return ''
    return attachments
      .map((a) => `[Attached file: "${a.filename}"]\n\`\`\`\n${a.content}\n\`\`\``)
      .join('\n\n')
  }, [attachments])

  return {
    attachments,
    uploading,
    uploadError,
    addFile,
    removeAttachment,
    clearAttachments,
    serializeForPrompt,
  }
}

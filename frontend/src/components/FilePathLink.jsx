import { memo, useCallback } from 'react'
import { FolderOpen } from 'lucide-react'
import { filesAPI } from '../services/api'

/**
 * Regex to detect Windows/Unix absolute file paths with an extension.
 * Matches: D:\folder\file.docx, C:/Users/test/file.pdf, /home/user/file.txt
 */
const FILE_PATH_RE = /([A-Z]:[\\\/][^\s"'<>*?|]+\.\w{1,6}|\/(?:home|tmp|var|opt|usr)[^\s"'<>*?|]+\.\w{1,6})/gi

/**
 * Split text into segments: plain text and file paths.
 */
function splitFilePaths(text) {
  if (!text || typeof text !== 'string') return [{ type: 'text', value: text || '' }]

  const segments = []
  let lastIndex = 0

  for (const match of text.matchAll(FILE_PATH_RE)) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', value: text.slice(lastIndex, match.index) })
    }
    segments.push({ type: 'path', value: match[0] })
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    segments.push({ type: 'text', value: text.slice(lastIndex) })
  }

  return segments.length > 0 ? segments : [{ type: 'text', value: text }]
}

/**
 * Clickable file path badge — clicking reveals file in Explorer.
 */
function PathBadge({ path }) {
  const filename = path.split(/[\\\/]/).pop()

  const handleClick = useCallback(async (e) => {
    e.preventDefault()
    try {
      await filesAPI.reveal(path)
    } catch (err) {
      console.error('[FilePathLink] Failed to reveal:', err)
    }
  }, [path])

  return (
    <button
      className="file-path-link"
      onClick={handleClick}
      title={path}
    >
      <FolderOpen size={13} />
      <span>{filename}</span>
    </button>
  )
}

/**
 * Render text with file paths replaced by clickable PathBadge components.
 * Use as a wrapper for text content in markdown rendering.
 */
function FilePathLink({ children }) {
  if (typeof children !== 'string') return children

  const segments = splitFilePaths(children)
  if (segments.length === 1 && segments[0].type === 'text') return children

  return (
    <>
      {segments.map((seg, i) =>
        seg.type === 'path'
          ? <PathBadge key={i} path={seg.value} />
          : seg.value
      )}
    </>
  )
}

export default memo(FilePathLink)
export { splitFilePaths }

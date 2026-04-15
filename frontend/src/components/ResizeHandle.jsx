import { useCallback, useRef, useEffect } from 'react'

/**
 * ResizeHandle — draggable divider between panels.
 *
 * Props:
 *  - onResize(deltaX): called with pixel delta while dragging
 *  - onResizeEnd(): called when drag finishes
 *  - direction: 'vertical' (default) — a vertical bar the user drags left/right
 */
export default function ResizeHandle({ onResize, onResizeEnd, direction = 'vertical' }) {
  const dragging = useRef(false)
  const lastX = useRef(0)

  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    dragging.current = true
    lastX.current = e.clientX
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!dragging.current) return
      const delta = e.clientX - lastX.current
      lastX.current = e.clientX
      onResize(delta)
    }

    const handleMouseUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      onResizeEnd?.()
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [onResize, onResizeEnd])

  return (
    <div
      className={`resize-handle resize-handle-${direction}`}
      onMouseDown={handleMouseDown}
    />
  )
}

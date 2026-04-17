/**
 * Wikilink detection — mirrors backend/app/graph/link_extractor.py regex.
 * Used for real-time graph edge updates while editing markdown.
 */

// Same regex as backend link_extractor.py line 9
const WIKILINK_RE = /(?<!!)\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]/g

/**
 * Extract wikilink targets from markdown text.
 * Returns deduplicated array of target strings (trimmed).
 */
export function extractWikilinkTargets(markdown) {
  if (!markdown) return []
  const targets = new Set()
  WIKILINK_RE.lastIndex = 0
  let match
  while ((match = WIKILINK_RE.exec(markdown)) !== null) {
    const target = match[1].trim()
    if (target) targets.add(target)
  }
  return [...targets]
}

/**
 * Resolve wikilink targets to node IDs using fuzzy matching
 * (mirrors backend/app/graph/builder.py _resolve_link_target).
 *
 * Pass 1: exact stem match (label without extension)
 * Pass 2: starts-with
 * Pass 3: substring
 */
export function resolveWikilinkTargets(targets, nodes) {
  const resolved = []
  for (const target of targets) {
    const tLower = target.toLowerCase()
    // Pass 1: exact
    let found = nodes.find((n) => {
      const stem = (n.label || '').toLowerCase().replace(/\.[a-z0-9]+$/, '')
      return stem === tLower || (n.label || '').toLowerCase() === tLower
    })
    // Pass 2: starts-with
    if (!found) {
      found = nodes.find((n) => {
        const stem = (n.label || '').toLowerCase().replace(/\.[a-z0-9]+$/, '')
        return stem.startsWith(tLower)
      })
    }
    // Pass 3: substring
    if (!found) {
      found = nodes.find((n) => (n.label || '').toLowerCase().includes(tLower))
    }
    if (found) resolved.push(found.id)
  }
  return [...new Set(resolved)]
}

const API_BASE = ''

/**
 * Call the SSE streaming endpoint. Yields parsed JSON events.
 */
export async function* streamChat(message, userId = 'default_user') {
  const url = `${API_BASE}/chat/stream?message=${encodeURIComponent(message)}&user_id=${encodeURIComponent(userId)}`

  const response = await fetch(url, {
    headers: { Accept: 'text/event-stream' },
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ${response.status}: ${text}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE messages separated by double newline
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6)
          try {
            yield JSON.parse(jsonStr)
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  }
}

/**
 * Call the one-shot POST /chat endpoint.
 */
export async function postChat(message, userId = 'default_user') {
  const url = `${API_BASE}/chat`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, user_id: userId }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ${response.status}: ${text}`)
  }

  return response.json()
}

import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamChat } from './api'

export default function App() {
  const [messages, setMessages] = useState([])          // { role, parts }
  const [streamParts, setStreamParts] = useState([])    // [{ type, ... }]
  const [isStreaming, setIsStreaming] = useState(false)
  const [input, setInput] = useState(
    '研究远程办公对员工生产力的影响。请使用研究综合技能进行全面分析。'
  )

  const chatEndRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamParts])

  const handleSend = useCallback(async () => {
    const msg = input.trim()
    if (!msg || isStreaming) return

    setInput('')
    setStreamParts([])
    setIsStreaming(true)

    setMessages(prev => [...prev, { role: 'user', parts: [{ type: 'text', text: msg }] }])

    const cancelled = { current: false }
    abortRef.current = () => { cancelled.current = true }

    try {
      const parts = []

      const emit = (part) => {
        if (cancelled.current) return
        const last = parts.length > 0 ? parts[parts.length - 1] : null
        // Merge consecutive text parts
        if (part.type === 'text' && last && last.type === 'text') {
          last.text += part.text
        }
        // Merge consecutive thoughts into one block
        else if (part.type === 'thought' && last && last.type === 'thought') {
          last.raw += '\n' + part.raw
          last.narrated = part.narrated || last.narrated
        }
        else {
          parts.push(part)
        }
        setStreamParts([...parts])
      }

      for await (const event of streamChat(msg)) {
        if (cancelled.current) break

        switch (event.type) {
          case 'text':
            emit({ type: 'text', text: event.text })
            break

          case 'thought':
            emit({
              type: 'thought',
              raw: event.raw,
              narrated: event.narrated,
            })
            break

          case 'narrator_card':
            emit({ type: 'card', card: event.card })
            break

          case 'done':
            break
        }
      }

      if (!cancelled.current) {
        setMessages(prev => [...prev, { role: 'assistant', parts: [...parts] }])
      }
    } catch (err) {
      if (!cancelled.current) {
        setMessages(prev => [...prev, {
          role: 'error',
          parts: [{ type: 'text', text: `请求失败: ${err.message}` }],
        }])
      }
    } finally {
      setStreamParts([])
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming])

  const handleStop = () => {
    abortRef.current?.()
    setIsStreaming(false)
    if (streamParts.length > 0) {
      setMessages(prev => [...prev, { role: 'assistant', parts: [...streamParts] }])
      setStreamParts([])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="app">
      {/* ---- Header ---- */}
      <header className="header">
        <h1>技能过程解说 Agent</h1>
        <span className="header-desc">实时展示 Agent 的思考、工具调用与回复</span>
      </header>

      {/* ---- Body ---- */}
      <div className="body">
        <div className="chat-panel chat-panel--full">
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg msg-${m.role}`}>
                <div className="msg-role">
                  {m.role === 'user' ? '你' : m.role === 'assistant' ? 'Agent' : '错误'}
                </div>
                <div className="msg-parts">
                  {m.parts.map((p, j) => renderPart(p, j))}
                </div>
              </div>
            ))}

            {/* Streaming */}
            {streamParts.length > 0 && (
              <div className="msg msg-assistant">
                <div className="msg-role">Agent</div>
                <div className="msg-parts">
                  {streamParts.map((p, j) => (
                    <span key={j}>{renderPart(p, j)}</span>
                  ))}
                  <span className="cursor-blink">|</span>
                </div>
              </div>
            )}

            {isStreaming && streamParts.length === 0 && (
              <div className="msg msg-assistant">
                <div className="msg-role">Agent</div>
                <div className="msg-content thinking-dots">思考中<span className="dots"/></div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="chat-input-area">
            <textarea
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，例如：逐步分析销售数据"
              rows={2}
              disabled={isStreaming}
            />
            <div className="chat-buttons">
              {isStreaming ? (
                <button className="btn btn-stop" onClick={handleStop}>停止</button>
              ) : (
                <button className="btn btn-send" onClick={handleSend} disabled={!input.trim()}>发送</button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Part renderers
// ---------------------------------------------------------------------------

function renderPart(part, key) {
  switch (part.type) {
    case 'text':
      return (
        <div className="part-text" key={key}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{part.text}</ReactMarkdown>
        </div>
      )

    case 'thought':
      return (
        <details className="part-thought" key={key}>
          <summary className="thought-summary">
            {part.narrated || part.raw.slice(0, 50) + '…'}
          </summary>
          <div className="thought-body">{part.raw}</div>
        </details>
      )

    case 'card': {
      const card = part.card
      const phase = card.phase
      const icon = card.icon || ''
      const label = card.label || ''
      const detail = card.detail || ''

      if (phase === 'before_tool') {
        return (
          <div className="part-card part-card--running" key={key}>
            <div className="part-card-head">
              ⏺ {icon} {label}
            </div>
            {card.args && <div className="part-card-args">参数: {card.args}</div>}
            {detail && <div className="part-card-detail">{detail}</div>}
          </div>
        )
      }

      if (phase === 'after_tool') {
        return (
          <div className="part-card part-card--done" key={key}>
            <div className="part-card-head">
              ✓ {icon} {label}
            </div>
            {detail && <div className="part-card-detail">{detail}</div>}
          </div>
        )
      }

      // thinking / other
      return (
        <div className="part-card part-card--info" key={key}>
          <div className="part-card-head">
            ⏺ {icon} {label}
          </div>
          {detail && <div className="part-card-detail">{detail}</div>}
        </div>
      )
    }

    default:
      return null
  }
}

import { useEffect, useRef, useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Send,
  Wrench,
  FileText,
  Brain,
  Search,
  X,
  Plus,
  BookOpen,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  logApi,
  streamOptimize,
  type LogInfo,
  type OptimizeEvent,
  type OptimizeToolCallInfo,
} from "../api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolStep {
  step_id: string;
  summary: string;
  calls: OptimizeToolCallInfo[];
}

// 时序项：思考 / 正文 / 工具，按到达顺序排列，连续思考合并为一项
type TimelineItem =
  | { kind: "thought"; text: string }
  | { kind: "text"; text: string }
  | { kind: "tool"; step: ToolStep };

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timeline: TimelineItem[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ToolStepCard({ step }: { step: ToolStep }) {
  const [open, setOpen] = useState(true);
  const isRunning = step.calls.some((c) => c.status === "running");

  return (
    <div className="my-1.5 rounded-xl border border-indigo-100 bg-indigo-50/60 text-sm overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-indigo-50 transition-colors"
      >
        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin flex-shrink-0" />
        ) : (
          <Wrench className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
        )}
        <span className="font-medium text-indigo-800 flex-1 truncate">{step.summary}</span>
        <span className="text-xs text-indigo-400 mr-1">{step.calls.length} 次调用</span>
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
        )}
      </button>

      {open && (
        <div className="border-t border-indigo-100 divide-y divide-indigo-100">
          {step.calls.map((call) => (
            <ToolCallRow key={call.id} call={call} />
          ))}
        </div>
      )}
    </div>
  );
}

function ToolCallRow({ call }: { call: OptimizeToolCallInfo }) {
  const [open, setOpen] = useState(false);

  const statusIcon =
    call.status === "running" ? (
      <Loader2 className="w-3 h-3 text-indigo-400 animate-spin" />
    ) : call.status === "error" ? (
      <span className="text-red-500 text-xs">✗</span>
    ) : (
      <span className="text-green-600 text-xs">✓</span>
    );

  return (
    <div className="px-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full py-1.5 text-left"
      >
        {statusIcon}
        <span className="text-xs text-gray-700 font-medium">
          {call.display_name || call.tool_name}
        </span>
        {open ? (
          <ChevronDown className="w-3 h-3 text-gray-400 ml-auto" />
        ) : (
          <ChevronRight className="w-3 h-3 text-gray-400 ml-auto" />
        )}
      </button>

      {open && (
        <div className="pb-2 space-y-1.5">
          {call.args_summary && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">参数</p>
              <pre className="text-xs bg-white/70 rounded p-2 overflow-auto max-h-32 whitespace-pre-wrap">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(call.args_summary), null, 2);
                  } catch {
                    return call.args_summary;
                  }
                })()}
              </pre>
            </div>
          )}
          {call.result_summary && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">结果</p>
              <pre className="text-xs bg-white/70 rounded p-2 overflow-auto max-h-32 whitespace-pre-wrap">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(call.result_summary), null, 2);
                  } catch {
                    return call.result_summary;
                  }
                })()}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ThoughtBubble({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        <Brain className="w-3.5 h-3.5" />
        <span>思考过程</span>
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="mt-1 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs text-gray-500 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
          {text}
        </div>
      )}
    </div>
  );
}

function MarkdownContent({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        h1: ({ children }) => <h1 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mb-1.5 mt-2 first:mt-0">{children}</h3>,
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:text-indigo-700 underline"
          >
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-gray-300 pl-3 text-gray-600 my-2">{children}</blockquote>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 overflow-x-auto text-xs my-2">
                <code>{children}</code>
              </pre>
            );
          }
          return (
            <code className="bg-gray-100 text-indigo-600 px-1.5 py-0.5 rounded text-[13px] border border-gray-200">
              {children}
            </code>
          );
        },
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="w-full text-left border-collapse text-[13px]">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="border-b border-gray-300 text-gray-500">{children}</thead>
        ),
        th: ({ children }) => <th className="py-2 px-3 font-medium">{children}</th>,
        td: ({ children }) => (
          <td className="py-2 px-3 border-b border-gray-100">{children}</td>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function AssistantBubble({ msg }: { msg: ChatMessage }) {
  const isStreaming = msg.timeline.length === 0;
  const lastItem = msg.timeline[msg.timeline.length - 1];
  return (
    <div className="flex flex-col gap-0.5">
      {msg.timeline.map((item, i) => {
        if (item.kind === "thought") {
          return <ThoughtBubble key={`th-${i}`} text={item.text} />;
        }
        if (item.kind === "tool") {
          return <ToolStepCard key={item.step.step_id} step={item.step} />;
        }
        const isLastText = item === lastItem;
        return (
          <div
            key={`tx-${i}`}
            className="rounded-xl bg-white border border-gray-200 px-4 py-3 text-sm text-gray-800 leading-relaxed"
          >
            <MarkdownContent text={item.text} />
            {isLastText && isStreaming && <span className="animate-pulse">▌</span>}
          </div>
        );
      })}
      {isStreaming && (
        <div className="rounded-xl bg-white border border-gray-200 px-4 py-3 text-sm text-gray-400 leading-relaxed">
          <span className="animate-pulse">▌</span>
        </div>
      )}
    </div>
  );
}

function UserBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-xl bg-indigo-600 px-4 py-3 text-sm text-white whitespace-pre-wrap">
        {msg.content}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OptimizePage() {
  // ---- Step 1: log search & selection ----
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<LogInfo[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedLogFiles, setSelectedLogFiles] = useState<Set<string>>(new Set());

  // ---- Step 2: chat ----
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);

  const stopStreamRef = useRef<(() => void) | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load initial log list on mount
  useEffect(() => {
    loadLogs("");
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadLogs = useCallback(async (q: string) => {
    setSearchLoading(true);
    try {
      const results = await logApi.list(30, q);
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    }
    setSearchLoading(false);
  }, []);

  // Debounced search
  function handleSearchChange(value: string) {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => loadLogs(value), 300);
  }

  function toggleLogFile(filename: string) {
    setSelectedLogFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  }

  function removeLogFile(filename: string) {
    setSelectedLogFiles((prev) => {
      const next = new Set(prev);
      next.delete(filename);
      return next;
    });
  }

  function handleSend() {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg: ChatMessage = { role: "user", content: text, timeline: [] };
    const assistantMsg: ChatMessage = { role: "assistant", content: "", timeline: [] };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setStreaming(true);

    const logFiles = Array.from(selectedLogFiles);

    const stop = streamOptimize(
      text,
      [],
      logFiles,
      (evt: OptimizeEvent) => {
        setMessages((prev) => {
          const msgs = [...prev];
          const last = { ...msgs[msgs.length - 1] };
          const timeline = [...last.timeline];
          const tail = timeline[timeline.length - 1];

          if (evt.type === "text") {
            if (tail && tail.kind === "text") {
              // 连续正文合并到同一段
              timeline[timeline.length - 1] = { kind: "text", text: tail.text + evt.text };
            } else {
              timeline.push({ kind: "text", text: evt.text });
            }
          } else if (evt.type === "thought") {
            const chunk = evt.narrated || evt.raw;
            if (tail && tail.kind === "thought") {
              // 连续思考拼接为同一张卡片
              timeline[timeline.length - 1] = { kind: "thought", text: tail.text + chunk };
            } else {
              timeline.push({ kind: "thought", text: chunk });
            }
          } else if (evt.type === "tool_step") {
            const idx = timeline.findIndex(
              (it) => it.kind === "tool" && it.step.step_id === evt.step_id
            );
            if (idx >= 0) {
              timeline[idx] = {
                kind: "tool",
                step: { step_id: evt.step_id, summary: evt.summary, calls: evt.calls },
              };
            } else {
              timeline.push({
                kind: "tool",
                step: { step_id: evt.step_id, summary: evt.summary, calls: evt.calls },
              });
            }
          } else if (evt.type === "tool_call") {
            const idx = timeline.findIndex(
              (it) => it.kind === "tool" && it.step.step_id === evt.step_id
            );
            if (idx >= 0 && timeline[idx].kind === "tool") {
              const step = (timeline[idx] as { kind: "tool"; step: ToolStep }).step;
              timeline[idx] = {
                kind: "tool",
                step: {
                  ...step,
                  calls: step.calls.map((c) =>
                    c.id === evt.call_id
                      ? {
                          ...c,
                          status: evt.status as OptimizeToolCallInfo["status"],
                          result_summary: evt.result_summary,
                        }
                      : c
                  ),
                },
              };
            }
          } else if (evt.type === "error") {
            const errText = `\n\n⚠️ 错误: ${evt.message}`;
            if (tail && tail.kind === "text") {
              timeline[timeline.length - 1] = { kind: "text", text: tail.text + errText };
            } else {
              timeline.push({ kind: "text", text: errText });
            }
          }

          last.timeline = timeline;
          msgs[msgs.length - 1] = last;
          return msgs;
        });
      },
      () => setStreaming(false)
    );

    stopStreamRef.current = stop;
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const contextCount = selectedLogFiles.size;

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* ================================================================
          Left panel — Step 1: 组建上下文
      ================================================================ */}
      <aside className="w-72 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col overflow-hidden">

        {/* ---- Step 1a: Log search ---- */}
        <div className="flex-shrink-0 p-3 border-b border-gray-200">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-5 h-5 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold flex-shrink-0">1</div>
            <h2 className="text-xs font-semibold text-gray-700">搜索日志</h2>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="关键词搜索（用户问题）"
              className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300"
            />
            {searchLoading && (
              <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-indigo-400 animate-spin" />
            )}
          </div>
        </div>

        {/* ---- Log results list ---- */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {searchResults.length === 0 && !searchLoading ? (
            <p className="text-xs text-gray-400 px-3 py-3">暂无日志</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {searchResults.map((log) => {
                const selected = selectedLogFiles.has(log.filename);
                return (
                  <div
                    key={log.filename}
                    className={`flex items-start gap-2 px-3 py-2.5 hover:bg-gray-100 transition-colors ${selected ? "bg-indigo-50" : ""}`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-700 truncate">
                        {log.date} {log.time}
                      </p>
                      <p className="text-xs text-gray-400 truncate mt-0.5">
                        {log.user_message || "(无消息)"}
                      </p>
                      <div className="flex gap-1.5 mt-1">
                        {log.elapsed_seconds > 0 && (
                          <span className="text-xs text-gray-300">{log.elapsed_seconds.toFixed(0)}s</span>
                        )}
                        {log.event_count > 0 && (
                          <span className="text-xs text-gray-300">{log.event_count}事件</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => toggleLogFile(log.filename)}
                      title={selected ? "从上下文移除" : "加入上下文"}
                      className={`flex-shrink-0 mt-0.5 rounded-md p-0.5 transition-colors ${
                        selected
                          ? "text-indigo-600 bg-indigo-100 hover:bg-indigo-200"
                          : "text-gray-400 hover:text-indigo-600 hover:bg-indigo-50"
                      }`}
                    >
                      {selected ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ---- Selected logs ---- */}
        {selectedLogFiles.size > 0 && (
          <div className="flex-shrink-0 border-t border-gray-200 p-3 bg-white">
            <div className="flex items-center gap-1.5 mb-2">
              <FileText className="w-3.5 h-3.5 text-indigo-500" />
              <span className="text-xs font-semibold text-gray-700">已选日志</span>
              <span className="ml-auto text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full font-medium">
                {selectedLogFiles.size}
              </span>
            </div>
            <div className="space-y-1 max-h-28 overflow-y-auto">
              {Array.from(selectedLogFiles).map((filename) => (
                <div
                  key={filename}
                  className="flex items-center gap-1.5 bg-indigo-50 border border-indigo-100 rounded-lg px-2 py-1"
                >
                  <span className="text-xs text-indigo-700 flex-1 truncate font-mono">
                    {filename.slice(0, 23)}…
                  </span>
                  <button
                    onClick={() => removeLogFile(filename)}
                    className="text-indigo-400 hover:text-indigo-600 flex-shrink-0"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

      </aside>

      {/* ================================================================
          Right panel — Step 2: 对话式优化
      ================================================================ */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-3 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold flex-shrink-0">2</div>
            <h1 className="text-base font-semibold text-gray-900">对话式优化</h1>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 pl-7">
            {contextCount > 0
              ? `已注入上下文：${selectedLogFiles.size} 条日志`
              : "在左侧选择日志后，告诉优化助手你想改进的方向"}
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <BookOpen className="w-10 h-10 mb-3 opacity-30" />
              <p className="text-sm font-medium">两步完成优化</p>
              <div className="mt-3 space-y-1.5 text-xs text-center opacity-80">
                <p>① 左侧搜索并选择相关日志文件（Step 1）</p>
                <p>② 在下方描述优化方向，Agent 自动读取日志并修改（Step 2）</p>
              </div>
              <p className="text-xs mt-4 opacity-50">
                例如：「根据以上日志，优化 searxng 的错误处理」
              </p>
            </div>
          )}

          {messages.map((msg, i) =>
            msg.role === "user" ? (
              <UserBubble key={i} msg={msg} />
            ) : (
              <AssistantBubble key={i} msg={msg} />
            )
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Context badges + input */}
        <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-3">
          {/* Context summary */}
          {contextCount > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {Array.from(selectedLogFiles).map((filename) => (
                <span
                  key={filename}
                  className="inline-flex items-center gap-1 text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5"
                >
                  <FileText className="w-3 h-3" />
                  {filename.slice(9, 22)}
                  <button onClick={() => removeLogFile(filename)} className="hover:text-indigo-900">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          {contextCount === 0 && (
            <p className="text-xs text-amber-600 mb-2 px-1">
              提示：请先在左侧选择日志文件作为优化的参考
            </p>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述优化方向，例如：「根据以上日志，优化 arxiv-paper-search 的关键词提取策略」（Enter 发送）"
              rows={3}
              className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              disabled={streaming}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || streaming}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {streaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

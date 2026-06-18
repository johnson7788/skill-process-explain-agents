import { useState, useEffect } from "react";
import {
  FileText, BarChart3, AlertTriangle, Loader2, Brain,
  MessageSquare, Clock, Wrench, ChevronDown, ChevronUp,
  CheckCircle, XCircle, ArrowLeft,
} from "lucide-react";
import { logApi, type LogInfo, type LogDetail, type LogAnalysis } from "../api";

type View = "list" | "detail" | "analysis";
type DetailTab = "overview" | "thought" | "response" | "timeline";

// ---- 小组件 ----

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function Collapsible({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 bg-gray-50 hover:bg-gray-100 text-sm font-semibold text-gray-700"
      >
        {title}
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && <div className="bg-white px-5 py-4">{children}</div>}
    </div>
  );
}

// ---- 详情标签页 ----

function OverviewTab({ log }: { log: LogDetail }) {
  const totalTime = log.summary.elapsed_seconds;
  return (
    <div className="space-y-4">
      {/* 基本信息 */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="总耗时" value={`${log.summary.elapsed_seconds.toFixed(1)}s`} />
        <StatCard label="思考 Tokens" value={log.summary.thought_count} />
        <StatCard label="输出字符数" value={log.summary.text_len} />
        <StatCard label="工具调用步骤" value={log.summary.step_count} />
        <StatCard label="总事件数" value={log.total_events} />
        <StatCard label="错误数" value={log.errors.length} sub={log.errors.length > 0 ? "有错误" : "无错误"} />
      </div>

      {/* 用户消息 */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
        <div className="text-xs text-indigo-500 mb-1 font-medium">用户提问</div>
        <div className="text-sm text-indigo-900">{log.meta.message || "（无内容）"}</div>
      </div>

      {/* 事件类型分布 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-gray-400" />
          事件类型分布
        </h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(log.event_types)
            .sort((a, b) => b[1] - a[1])
            .map(([type, count]) => {
              const colors: Record<string, string> = {
                thought: "bg-purple-100 text-purple-700",
                text: "bg-green-100 text-green-700",
                tool_call: "bg-blue-100 text-blue-700",
                tool_step: "bg-cyan-100 text-cyan-700",
                error: "bg-red-100 text-red-700",
                meta: "bg-gray-100 text-gray-600",
                summary: "bg-gray-100 text-gray-600",
                done: "bg-gray-100 text-gray-600",
              };
              return (
                <span key={type} className={`px-3 py-1 rounded-full text-xs font-medium ${colors[type] ?? "bg-gray-100 text-gray-600"}`}>
                  {type}: {count}
                </span>
              );
            })}
        </div>
      </div>

      {/* 时间线阶段简览 */}
      {log.timeline_phases.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            阶段耗时
          </h3>
          <div className="space-y-2">
            {log.timeline_phases.map((p) => {
              const pct = totalTime > 0 ? ((p.end_offset - p.start_offset) / totalTime) * 100 : 0;
              const phaseColor: Record<string, string> = {
                思考: "bg-purple-400",
                工具调用: "bg-blue-400",
                输出: "bg-green-400",
              };
              return (
                <div key={p.phase} className="flex items-center gap-3">
                  <span className="text-xs w-16 text-gray-500">{p.phase}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                    <div
                      className={`${phaseColor[p.phase] ?? "bg-gray-400"} h-full rounded-full`}
                      style={{ width: `${Math.max(pct, 2)}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-24 text-right">
                    {p.start_offset.toFixed(1)}s – {p.end_offset.toFixed(1)}s
                  </span>
                  <span className="text-xs text-gray-400 w-16 text-right">{p.token_count} tokens</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 错误 */}
      {log.errors.length > 0 && (
        <div className="bg-white rounded-xl border border-red-200 p-5">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-4 h-4" />
            错误记录
          </h3>
          <div className="space-y-2">
            {log.errors.map((err, i) => (
              <div key={i} className="p-3 bg-red-50 rounded-lg text-sm text-red-700 font-mono">
                {err.error ?? err.message ?? JSON.stringify(err)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 工具步骤 */}
      {log.tool_steps.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Wrench className="w-4 h-4 text-gray-400" />
            工具调用步骤
          </h3>
          <div className="space-y-3">
            {log.tool_steps.map((step, i) => (
              <Collapsible key={i} title={`步骤 ${i + 1}${step.summary ? " — " + step.summary : ""}`}>
                <div className="space-y-2">
                  {step.calls.map((c, j) => (
                    <div key={j} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                      {c.status === "success" || c.status === "done"
                        ? <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                        : c.status === "error" || c.status === "failed"
                        ? <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                        : <div className="w-4 h-4 rounded-full bg-gray-300 mt-0.5 shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-mono font-medium text-gray-800">{c.tool}</div>
                        {c.args_summary && (
                          <div className="text-xs text-gray-500 mt-0.5 truncate">参数: {c.args_summary}</div>
                        )}
                        {c.result_summary && (
                          <div className="text-xs text-gray-600 mt-1 whitespace-pre-wrap">{c.result_summary}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </Collapsible>
            ))}
          </div>
        </div>
      )}

      {/* 旧式 tool_calls */}
      {log.tool_steps.length === 0 && log.tool_calls.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Wrench className="w-4 h-4 text-gray-400" />
            工具调用记录
          </h3>
          <div className="space-y-2">
            {log.tool_calls.map((tc, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <span className={`w-2 h-2 rounded-full shrink-0 ${tc.status === "success" ? "bg-green-400" : "bg-red-400"}`} />
                <span className="text-sm font-mono font-medium">{tc.tool}</span>
                <span className="text-xs text-gray-400 flex-1 truncate">{tc.args_preview}</span>
                <span className={`text-xs shrink-0 ${tc.status === "success" ? "text-green-600" : "text-red-600"}`}>{tc.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ThoughtTab({ log }: { log: LogDetail }) {
  const thoughtCount = log.event_types["thought"] ?? 0;
  const thoughtText = log.full_thought;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Brain className="w-4 h-4 text-purple-500" />
        <span className="text-sm font-semibold text-gray-700">完整思考内容</span>
        <span className="text-xs text-gray-400">({thoughtCount} tokens)</span>
      </div>
      {thoughtText ? (
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-5 text-sm text-purple-900 whitespace-pre-wrap leading-relaxed max-h-[70vh] overflow-y-auto font-sans">
          {thoughtText}
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400 text-sm">无思考内容</div>
      )}
    </div>
  );
}

function ResponseTab({ log }: { log: LogDetail }) {
  const text = log.full_response_text;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <MessageSquare className="w-4 h-4 text-green-500" />
        <span className="text-sm font-semibold text-gray-700">完整回复内容</span>
        <span className="text-xs text-gray-400">({text.length} 字符)</span>
      </div>
      {text ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed max-h-[70vh] overflow-y-auto">
          {text}
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400 text-sm">无回复内容</div>
      )}
    </div>
  );
}

function TimelineTab({ log }: { log: LogDetail }) {
  const totalTime = log.summary.elapsed_seconds;
  const phases = log.timeline_phases;
  const phaseColor: Record<string, { bar: string; dot: string; text: string }> = {
    思考: { bar: "bg-purple-400", dot: "bg-purple-500", text: "text-purple-700" },
    工具调用: { bar: "bg-blue-400", dot: "bg-blue-500", text: "text-blue-700" },
    输出: { bar: "bg-green-400", dot: "bg-green-500", text: "text-green-700" },
  };

  return (
    <div className="space-y-6">
      {/* 可视化时间线 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold mb-4">时间轴（0 → {totalTime.toFixed(1)}s）</h3>
        <div className="relative h-12 bg-gray-100 rounded-lg overflow-hidden">
          {phases.map((p) => {
            const left = totalTime > 0 ? (p.start_offset / totalTime) * 100 : 0;
            const width = totalTime > 0 ? ((p.end_offset - p.start_offset) / totalTime) * 100 : 0;
            const c = phaseColor[p.phase] ?? { bar: "bg-gray-400", dot: "bg-gray-500", text: "text-gray-600" };
            return (
              <div
                key={p.phase}
                className={`absolute top-0 h-full ${c.bar} opacity-80 flex items-center justify-center`}
                style={{ left: `${left}%`, width: `${Math.max(width, 1)}%` }}
                title={`${p.phase}: ${p.start_offset.toFixed(1)}s – ${p.end_offset.toFixed(1)}s`}
              >
                {width > 8 && <span className="text-white text-xs font-medium truncate px-1">{p.phase}</span>}
              </div>
            );
          })}
        </div>
        {/* 图例 */}
        <div className="flex gap-4 mt-3">
          {phases.map((p) => {
            const c = phaseColor[p.phase] ?? { dot: "bg-gray-400", text: "text-gray-600" };
            return (
              <div key={p.phase} className="flex items-center gap-1.5">
                <span className={`w-3 h-3 rounded-sm ${c.dot}`} />
                <span className={`text-xs ${c.text} font-medium`}>{p.phase}</span>
                <span className="text-xs text-gray-400">
                  {(p.end_offset - p.start_offset).toFixed(1)}s · {p.token_count} tokens
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 阶段详情表格 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold mb-3">阶段详情</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-100">
              <th className="text-left pb-2">阶段</th>
              <th className="text-right pb-2">开始</th>
              <th className="text-right pb-2">结束</th>
              <th className="text-right pb-2">耗时</th>
              <th className="text-right pb-2">Tokens</th>
              <th className="text-right pb-2">占比</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {phases.map((p) => {
              const duration = p.end_offset - p.start_offset;
              const pct = totalTime > 0 ? (duration / totalTime) * 100 : 0;
              return (
                <tr key={p.phase}>
                  <td className="py-2 font-medium">{p.phase}</td>
                  <td className="py-2 text-right text-gray-500">{p.start_offset.toFixed(2)}s</td>
                  <td className="py-2 text-right text-gray-500">{p.end_offset.toFixed(2)}s</td>
                  <td className="py-2 text-right font-medium">{duration.toFixed(2)}s</td>
                  <td className="py-2 text-right text-gray-500">{p.token_count}</td>
                  <td className="py-2 text-right text-gray-500">{pct.toFixed(1)}%</td>
                </tr>
              );
            })}
            <tr className="border-t border-gray-200 font-medium">
              <td className="py-2">合计</td>
              <td />
              <td />
              <td className="py-2 text-right">{totalTime.toFixed(2)}s</td>
              <td className="py-2 text-right text-gray-500">
                {phases.reduce((s, p) => s + p.token_count, 0)}
              </td>
              <td className="py-2 text-right">100%</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 会话基本信息 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold mb-3">会话信息</h3>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <dt className="text-gray-500">Session ID</dt>
          <dd className="font-mono text-gray-800">{log.meta.session_id}</dd>
          <dt className="text-gray-500">用户 ID</dt>
          <dd className="font-mono text-gray-800">{log.meta.user_id}</dd>
          <dt className="text-gray-500">开始时间</dt>
          <dd className="text-gray-800">{log.meta.start_time}</dd>
          <dt className="text-gray-500">文件名</dt>
          <dd className="font-mono text-gray-800 text-xs">{log.filename}</dd>
        </dl>
      </div>
    </div>
  );
}

// ---- 主页面 ----

export default function LogsPage() {
  const [view, setView] = useState<View>("list");
  const [logs, setLogs] = useState<LogInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<LogDetail | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [analysis, setAnalysis] = useState<LogAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setLoading(true);
    try {
      setLogs(await logApi.list());
    } catch {
      // ignore
    }
    setLoading(false);
  };

  const handleViewLog = async (filename: string) => {
    setLoading(true);
    try {
      const detail = await logApi.get(filename);
      setSelectedLog(detail);
      setDetailTab("overview");
      setView("detail");
    } catch {
      // ignore
    }
    setLoading(false);
  };

  const handleAnalyze = async () => {
    if (analysis) { setView("analysis"); return; }
    setAnalysisLoading(true);
    try {
      setAnalysis(await logApi.analyze());
      setView("analysis");
    } catch {
      // ignore
    }
    setAnalysisLoading(false);
  };

  const detailTabs: { key: DetailTab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "概览", icon: <BarChart3 className="w-3.5 h-3.5" /> },
    { key: "thought", label: "思考过程", icon: <Brain className="w-3.5 h-3.5" /> },
    { key: "response", label: "回复内容", icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { key: "timeline", label: "时间线", icon: <Clock className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="p-6 max-w-6xl">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">日志分析</h1>
          <p className="text-sm text-gray-500 mt-1">查看会话日志，分析智能体表现</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setView("list"); loadLogs(); }}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg ${
              view === "list" ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            日志列表
          </button>
          <button
            onClick={handleAnalyze}
            disabled={analysisLoading}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg ${
              view === "analysis" ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {analysisLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
            全局分析
          </button>
        </div>
      </div>

      {/* 日志列表 */}
      {view === "list" && (
        <div className="space-y-2">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            </div>
          ) : (
            logs.map((log) => (
              <div
                key={log.filename}
                className="bg-white rounded-xl border border-gray-200 p-4 hover:border-indigo-300 hover:shadow-sm transition cursor-pointer"
                onClick={() => handleViewLog(log.filename)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                    <div>
                      <span className="text-sm font-semibold text-gray-900">{log.date} {log.time}</span>
                      <span className="text-xs text-gray-400 ml-3 font-mono">{log.session_id.slice(0, 12)}…</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span className="bg-gray-100 px-2 py-0.5 rounded">{log.event_count} 事件</span>
                    <span className="bg-gray-100 px-2 py-0.5 rounded">{log.elapsed_seconds.toFixed(1)}s</span>
                    <span className="bg-gray-100 px-2 py-0.5 rounded">{log.size_kb}KB</span>
                  </div>
                </div>
                {log.user_message && (
                  <p className="text-sm text-gray-500 mt-2 line-clamp-1 pl-7">
                    {log.user_message}
                  </p>
                )}
              </div>
            ))
          )}
          {!loading && logs.length === 0 && (
            <div className="text-center py-12 text-gray-400">暂无日志</div>
          )}
        </div>
      )}

      {/* 日志详情 */}
      {view === "detail" && (
        <div className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            </div>
          ) : selectedLog ? (
            <>
              {/* 面包屑 + 标题 */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setView("list")}
                  className="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800"
                >
                  <ArrowLeft className="w-4 h-4" />
                  返回列表
                </button>
                <span className="text-gray-300">/</span>
                <span className="text-sm text-gray-500 font-mono truncate">{selectedLog.filename}</span>
              </div>

              {/* 标签页导航 */}
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                {detailTabs.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setDetailTab(t.key)}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm rounded-md flex-1 justify-center transition ${
                      detailTab === t.key
                        ? "bg-white text-gray-900 font-medium shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    {t.icon}
                    {t.label}
                  </button>
                ))}
              </div>

              {/* 标签内容 */}
              {detailTab === "overview" && <OverviewTab log={selectedLog} />}
              {detailTab === "thought" && <ThoughtTab log={selectedLog} />}
              {detailTab === "response" && <ResponseTab log={selectedLog} />}
              {detailTab === "timeline" && <TimelineTab log={selectedLog} />}
            </>
          ) : null}
        </div>
      )}

      {/* 全局分析 */}
      {view === "analysis" && analysis && (
        <div className="space-y-4">
          {/* 统计卡片 */}
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="总会话数" value={analysis.summary.total_sessions} />
            <StatCard label="工具调用总次数" value={analysis.summary.total_tool_calls} />
            <StatCard label="工具成功率" value={analysis.summary.success_rate} />
            <StatCard label="平均响应耗时" value={`${analysis.summary.avg_elapsed_seconds}s`} />
            <StatCard label="总事件数" value={analysis.summary.total_events} />
            <StatCard label="失败工具调用" value={analysis.summary.failed_tool_calls} />
            <StatCard label="错误总数" value={analysis.summary.total_errors} />
          </div>

          {/* 工具使用分布 */}
          {Object.keys(analysis.tool_usage).length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold mb-3">工具使用频率</h3>
              <div className="space-y-2">
                {Object.entries(analysis.tool_usage).map(([tool, count]) => {
                  const max = Math.max(...Object.values(analysis.tool_usage));
                  return (
                    <div key={tool} className="flex items-center gap-3">
                      <span className="text-sm font-mono w-48 truncate text-gray-700">{tool}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div
                          className="bg-indigo-500 h-full rounded-full"
                          style={{ width: `${(count / max) * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-8 text-right text-gray-700">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 会话列表 */}
          {analysis.session_summaries.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold mb-3">各会话详情</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-100">
                      <th className="text-left pb-2 pr-4">时间</th>
                      <th className="text-left pb-2 pr-4">用户提问</th>
                      <th className="text-right pb-2 pr-4">耗时</th>
                      <th className="text-right pb-2 pr-4">思考</th>
                      <th className="text-right pb-2 pr-4">输出</th>
                      <th className="text-right pb-2 pr-4">工具</th>
                      <th className="text-right pb-2">错误</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {analysis.session_summaries.map((s) => (
                      <tr
                        key={s.filename}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => handleViewLog(s.filename)}
                      >
                        <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">{s.date} {s.time}</td>
                        <td className="py-2 pr-4 text-gray-700 max-w-xs truncate">{s.user_message || "—"}</td>
                        <td className="py-2 pr-4 text-right font-mono text-gray-600">{s.elapsed_seconds.toFixed(1)}s</td>
                        <td className="py-2 pr-4 text-right text-purple-600">{s.thought_tokens}</td>
                        <td className="py-2 pr-4 text-right text-green-600">{s.text_tokens}</td>
                        <td className="py-2 pr-4 text-right text-blue-600">{s.tool_calls}</td>
                        <td className="py-2 text-right">
                          {s.errors > 0
                            ? <span className="text-red-500 font-medium">{s.errors}</span>
                            : <span className="text-gray-300">0</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 错误详情 */}
          {analysis.error_details.length > 0 && (
            <Collapsible title={`错误详情（${analysis.error_details.length} 条）`}>
              <div className="space-y-2">
                {analysis.error_details.map((e, i) => (
                  <div key={i} className="p-3 bg-red-50 rounded-lg text-sm text-red-700">
                    <span className="font-mono text-xs text-gray-400 mr-2">{e.session.slice(0, 16)}…</span>
                    {e.error}
                  </div>
                ))}
              </div>
            </Collapsible>
          )}

          {/* 优化提示 */}
          {analysis.optimization_hints.length > 0 && (
            <div className="bg-white rounded-xl border border-amber-200 p-5">
              <h3 className="text-sm font-semibold mb-3 text-amber-700">优化建议</h3>
              <div className="space-y-2">
                {analysis.optimization_hints.map((hint, i) => (
                  <div key={i} className="p-3 bg-amber-50 rounded-lg text-sm text-amber-800">{hint}</div>
                ))}
              </div>
            </div>
          )}

          {/* 用户提问样例 */}
          {analysis.user_messages.length > 0 && (
            <Collapsible title={`用户提问样例（${analysis.user_messages.length} 条）`} defaultOpen>
              <div className="space-y-1">
                {analysis.user_messages.map((msg, i) => (
                  <div key={i} className="text-sm text-gray-600 p-2 bg-gray-50 rounded">{msg}</div>
                ))}
              </div>
            </Collapsible>
          )}
        </div>
      )}
    </div>
  );
}

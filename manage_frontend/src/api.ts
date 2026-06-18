/** 管理后端 API 客户端 */

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---- Skills（只读列表，供 Optimize 页面 skill 选择器）----

export interface SkillInfo {
  slug: string;
  name: string;
  description: string;
}

export const skillApi = {
  list: () => request<SkillInfo[]>("/skills"),
};

// ---- Logs ----

export interface LogInfo {
  filename: string;
  session_id: string;
  date: string;
  time: string;
  size_kb: number;
  event_count: number;
  elapsed_seconds: number;
  user_message: string;
}

export interface LogDetail {
  filename: string;
  meta: { session_id: string; user_id: string; message: string; start_time: string };
  summary: { elapsed_seconds: number; event_count: number; text_len: number; thought_count: number; step_count: number };
  total_events: number;
  event_types: Record<string, number>;
  full_thought: string;
  full_response_text: string;
  tool_calls: { tool: string; status: string; args_preview: string; result_preview: string }[];
  tool_steps: { step_id: string; summary: string; call_count: number; calls: { tool: string; status: string; args_summary: string; result_summary: string }[] }[];
  errors: { error?: string; message?: string }[];
  timeline_phases: { phase: string; start_offset: number; end_offset: number; token_count: number }[];
  narrator_cards: Record<string, unknown>[];
}

export interface LogAnalysis {
  summary: {
    total_sessions: number;
    total_events: number;
    avg_elapsed_seconds: number;
    total_tool_calls: number;
    failed_tool_calls: number;
    success_rate: string;
    total_errors: number;
  };
  tool_usage: Record<string, number>;
  user_messages: string[];
  failed_tool_details: { tool: string; status: string; session: string }[];
  error_details: { error: string; session: string }[];
  session_summaries: {
    filename: string;
    date: string;
    time: string;
    user_message: string;
    elapsed_seconds: number;
    thought_tokens: number;
    text_tokens: number;
    tool_calls: number;
    errors: number;
  }[];
  optimization_hints: string[];
}

// ---- Logs by skills ----

export interface SkillLogEntry {
  filename: string;
  date: string;
  time: string;
  user_message: string;
  relevant_tool_calls: { tool: string; status: string; args_preview: string; result_preview: string }[];
  errors: { error: string }[];
}

export const logApi = {
  list: (limit = 50, q = "") =>
    request<LogInfo[]>(`/logs?limit=${limit}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  get: (filename: string) => request<LogDetail>(`/logs/${filename}`),
  analyze: () => request<LogAnalysis>("/logs/analyze"),
  analyzeFile: (filename: string) => request<LogAnalysis>(`/logs/analyze/${filename}`),
  bySkills: (slugs: string[], limit = 10) =>
    request<SkillLogEntry[]>(
      `/logs/by-skills?skills=${encodeURIComponent(slugs.join(","))}&limit=${limit}`
    ),
};

// ---- Optimize chat (SSE — ADK protocol) ----

export interface OptimizeToolCallInfo {
  id: string;
  tool_name: string;
  display_name: string;
  args_summary: string;
  status: "running" | "done" | "error";
  result_summary: string | null;
}

export type OptimizeEvent =
  | { type: "text"; text: string }
  | { type: "thought"; raw: string; narrated: string }
  | { type: "tool_step"; step_id: string; summary: string; call_count: number; calls: OptimizeToolCallInfo[] }
  | { type: "tool_call"; step_id: string; call_id: string; status: string; result_summary: string }
  | { type: "done"; text_len: number; thought_count: number; step_count: number }
  | { type: "error"; message: string };

export function streamOptimize(
  message: string,
  skills: string[],
  logFiles: string[],
  onEvent: (evt: OptimizeEvent) => void,
  onClose: () => void
): () => void {
  const params = new URLSearchParams({
    message,
    skills: skills.join(","),
    log_files: logFiles.join(","),
  });
  const es = new EventSource(`/chat/optimize_stream?${params}`);

  es.onmessage = (e) => {
    try {
      const evt = JSON.parse(e.data) as OptimizeEvent;
      onEvent(evt);
      if (evt.type === "done" || evt.type === "error") {
        es.close();
        onClose();
      }
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = () => {
    es.close();
    onClose();
  };

  return () => es.close();
}

// ---- Status ----

export const statusApi = {
  get: () =>
    request<{
      backend_dir: string;
      skills_dir: string;
      logs_dir: string;
      skills_count: number;
      logs_count: number;
    }>("/status"),
};

import { ApiError, BASE, type Schemas } from "./client";

export type RoutingProgress = Schemas["RoutingProgress"];
export type RoutingEvent =
  | { type: "meta"; data: { request_id: string; session_id: string; show_progress: boolean; method: string } }
  | { type: "progress"; data: RoutingProgress }
  | { type: "result"; data: Schemas["AskResponse"] };

/** Incremental SSE parser: handles UTF-8, CRLF, comments and arbitrary network chunk boundaries. */
export async function askStream(body: Schemas["AskBody"], onEvent: (event: RoutingEvent) => void,
                                signal?: AbortSignal): Promise<Schemas["AskResponse"]> {
  const res = await fetch(BASE + "/api/v1/ask/stream", {
    method: "POST", credentials: "include", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body), signal,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, typeof data?.detail === "string" ? data.detail : "Could not submit this question.");
  }
  if (!res.body) throw new Error("Streaming is unavailable in this browser.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply: Schemas["AskResponse"] | undefined;
  let doneEvent = false;
  const dispatch = (frame: string) => {
    let kind = "message";
    const data: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) kind = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const parsed = JSON.parse(data.join("\n"));
    if (kind === "error") throw new Error(parsed.detail ?? "The selected model could not answer.");
    if (kind === "done") { doneEvent = true; return; }
    if (kind === "result") reply = parsed;
    if (kind === "meta" || kind === "progress" || kind === "result") {
      onEvent({ type: kind, data: parsed } as RoutingEvent);
    }
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
      }
      if (doneEvent || done) break;
    }
    if (!reply) throw new Error("The connection ended before an answer arrived. Please retry.");
    return reply;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

import { ApiError, failure, send, V2, type Schemas } from "./client";

export type RoutingProgress = Schemas["RoutingProgress"];
export type AskOut = Schemas["AskOut"];
export type RoutingEvent =
  | { type: "meta"; data: { request_id: string; conversation_id: string; show_progress: boolean; method: string } }
  | { type: "progress"; data: RoutingProgress }
  | { type: "token"; data: { text?: string } }
  | { type: "result"; data: AskOut };

/** Incremental SSE parser: handles UTF-8, CRLF, comments and arbitrary network chunk boundaries. */
export async function askStream(courseId: number, body: Schemas["AskIn"], onEvent: (event: RoutingEvent) => void,
                                signal?: AbortSignal): Promise<AskOut> {
  const res = await send("POST", `${V2}/courses/${courseId}/ask/stream`, { json: body, accept: "text/event-stream" }, signal);
  if (!res.ok) throw await failure(res);
  if (!res.body) throw new Error("Streaming is unavailable in this browser.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply: AskOut | undefined;
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
    if (kind === "error") throw new ApiError(503, parsed.detail ?? "The selected model could not answer.");
    if (kind === "done") { doneEvent = true; return; }
    if (kind === "result") reply = parsed;
    if (kind === "meta" || kind === "progress" || kind === "token" || kind === "result") {
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

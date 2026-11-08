"use client";

import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, askAboutPolicy, getVote } from "@/lib/api";
import "./Assistant.css";

const NAME = "RealNews Assistant";
const HINT_KEY = "votelens-assistant-hint-seen";

/** What the user is looking at, from the URL. Read from window so the layout can stay static. */
function pageContext(pathname) {
  const query = typeof window === "undefined" ? new URLSearchParams() : new URLSearchParams(window.location.search);
  const stateCode = query.get("state") ?? undefined;
  const [, kind, rawId] = pathname.match(/^\/(policy|vote|member|senator|state)\/([^/]+)/) ?? [];
  const id = rawId && decodeURIComponent(rawId);
  if (kind === "policy") return { kind: "policy", policyId: id, stateCode };
  if (kind === "vote") return { kind: "vote", voteId: id, stateCode };
  if (kind === "member" || kind === "senator") return { kind: "member", bioguideId: id };
  if (kind === "state") return { kind: "state", stateCode: id.toUpperCase() };
  return { kind: "home" };
}

const NO_POLICY = "I can only answer questions about a specific policy for now. Open a policy, or a vote on one, and ask me there.";

const COPY = {
  policy: {
    greeting: "Hello! Ask me anything about this policy and I'll answer from the official record.",
    prompts: ["What does this policy do?", "What has happened to it so far?", "How did the vote turn out?"],
  },
  vote: {
    greeting: "Hello! Ask me about the policy this roll call was on.",
    prompts: ["What does this policy do?"],
  },
  member: { greeting: "Hello! Open one of these votes and I can answer questions about the policy it was on.", prompts: [] },
  state: { greeting: "Hello! Open a vote or policy and I can answer questions about it.", prompts: [] },
  home: { greeting: "Hello! Pick a state and open a vote or policy, and I can answer questions about it.", prompts: [] },
};

function safeLink(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function Mascot({ size, className }) {
  return <Image className={className} src="/assistant/mascot.png" alt="" width={size} height={size} />;
}

export default function Assistant() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [hint, setHint] = useState(false);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [thread, setThread] = useState({ path: pathname, messages: [] });
  const launcher = useRef(null);
  const input = useRef(null);
  const log = useRef(null);
  const requestId = useRef(0);
  const wasOpen = useRef(false);

  // A new page is a new subject, so start a new conversation and drop any answer still on its way.
  if (thread.path !== pathname) {
    requestId.current += 1;
    setThread({ path: pathname, messages: [] });
    setPending(false);
  }

  const copy = COPY[pageContext(pathname).kind];

  useEffect(() => {
    try {
      if (sessionStorage.getItem(HINT_KEY)) return;
      sessionStorage.setItem(HINT_KEY, "1");
    } catch { /* storage can be blocked; the hint is optional */ }
    setHint(true);
    const timer = setTimeout(() => setHint(false), 6000);
    return () => clearTimeout(timer);
  }, []);

  // Runs after render because the launcher is hidden on phones while the panel is open.
  useEffect(() => {
    if (open) input.current?.focus();
    else if (wasOpen.current) launcher.current?.focus();
    wasOpen.current = open;
  }, [open]);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [thread, pending, open]);

  function close() {
    setOpen(false);
  }

  function add(message) {
    setThread((current) => ({ ...current, messages: [...current.messages, message] }));
  }

  async function ask(text) {
    const trimmed = text.trim();
    if (trimmed.length < 3 || pending) return;
    setQuestion("");
    add({ role: "user", text: trimmed });

    const context = pageContext(pathname);
    if (context.kind !== "policy" && context.kind !== "vote") {
      add({ role: "assistant", text: NO_POLICY });
      return;
    }

    const id = ++requestId.current;
    setPending(true);
    try {
      // A vote page has no policy in its URL, so look it up. The model is never called without one.
      const policyId = context.policyId ?? (await getVote(context.voteId)).policyId;
      if (id !== requestId.current) return;
      if (!policyId) {
        add({ role: "assistant", text: NO_POLICY });
        return;
      }
      const { stateCode } = context;
      const answer = await askAboutPolicy({ policyId, question: trimmed, ...(stateCode ? { stateCode } : {}) });
      if (id !== requestId.current) return;
      add({ role: "assistant", text: answer.answer, sources: answer.sources, model: answer.model });
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      if (id !== requestId.current) return;
      add({ role: "assistant", failed: true, text: "I can't answer right now. Please try again in a little while." });
    } finally {
      if (id === requestId.current) setPending(false);
    }
  }

  return (
    <div className="assistant">
      {open && (
        <section className="assistant-panel" role="dialog" aria-label={NAME}
          onKeyDown={(event) => { if (event.key === "Escape") close(); }}>
          <header className="assistant-header">
            <Mascot size={40} className="assistant-face" />
            <div>
              <strong>{NAME}</strong>
              <small>Answers from the official record</small>
            </div>
            <button type="button" className="assistant-close" onClick={close} aria-label="Close chat">×</button>
          </header>

          <div className="assistant-log" ref={log} role="log" aria-live="polite">
            <p className="assistant-msg from-assistant">{copy.greeting}</p>
            {thread.messages.map((message, index) => (
              <div key={index} className={"assistant-msg from-" + message.role + (message.failed ? " failed" : "")}>
                <p>{message.text}</p>
                {message.sources?.length > 0 && (
                  <details>
                    <summary>Sources</summary>
                    <ul>
                      {message.sources.map((source, i) => {
                        const url = safeLink(source);
                        return <li key={i}>{url ? <a href={url} target="_blank" rel="noreferrer">{source}</a> : source}</li>;
                      })}
                    </ul>
                  </details>
                )}
              </div>
            ))}
            {pending && (
              <p className="assistant-msg from-assistant assistant-typing" role="status">
                <span aria-hidden="true"><i /><i /><i /></span>
                <span className="assistant-sr">Finding an answer. This can take up to a minute.</span>
              </p>
            )}
            {!thread.messages.length && copy.prompts.length > 0 && (
              <div className="assistant-prompts">
                {copy.prompts.map((prompt) => <button type="button" key={prompt} onClick={() => ask(prompt)}>{prompt}</button>)}
              </div>
            )}
          </div>

          <form className="assistant-form" onSubmit={(event) => { event.preventDefault(); ask(question); }}>
            <label className="assistant-sr" htmlFor="assistant-question">Your question</label>
            <textarea id="assistant-question" ref={input} rows={1} maxLength={500} value={question}
              placeholder="Ask a question…" onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(question); }
              }} />
            <button className="button" type="submit" disabled={pending || question.trim().length < 3}>Ask</button>
          </form>
          <p className="assistant-note">AI-generated and can make mistakes. Check the official record.</p>
        </section>
      )}

      {hint && !open && <p className="assistant-hint" aria-hidden="true">Questions? Ask me!</p>}

      <button type="button" ref={launcher} className={"assistant-launcher" + (pending ? " thinking" : "")}
        aria-expanded={open} aria-label={open ? "Close " + NAME : "Open " + NAME}
        onClick={() => { setHint(false); if (open) close(); else setOpen(true); }}>
        <Mascot size={92} className="assistant-character" />
      </button>
    </div>
  );
}

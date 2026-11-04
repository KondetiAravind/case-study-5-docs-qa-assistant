
"use client";

import { useEffect, useState } from "react";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type DemoUser = {
  id: string;
  label: string;
  role: string;
};

type Source = {
  doc_id: string;
  title: string;
  chunk_id: string;
  chunk_index: number;
  excerpt: string;
  lexical_score: number;
  semantic_similarity: number;
  hybrid_score: number;
  lexical_rank: number | null;
  semantic_rank: number | null;
  hybrid_rank: number;
  is_cited: boolean;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  mode?: string;
  requestId?: string;
  showEvidence?: boolean;
  showDiagnostics?: boolean;
  status?: "answered" | "not_found" | "access_denied" | "error";
};

type AskResponse = {
  answer: string;
  sources?: Source[];
  mode?: string;
  request_id?: string;
  show_evidence?: boolean;
  show_diagnostics?: boolean;
  status?: "answered" | "not_found" | "access_denied" | "error";
};

const makeId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `chat_${Date.now()}_${Math.random().toString(36).slice(2)}`;

const fmt = (n: number) =>
  Number.isFinite(n) ? n.toFixed(4) : "—";

const FAQ_GROUPS = [
  {
    category: "Account & Security",
    questions: [
      "How do I reset my password?",
      "How long does a password reset link last?",
      "What are the password requirements?",
      "How do I configure Single Sign-On?",
    ],
  },
  {
    category: "Team Management",
    questions: [
      "How can I invite a new team member?",
      "What roles can I assign to team members?",
    ],
  },
  {
    category: "Reports & Exports",
    questions: [
      "How do I export a report to CSV?",
      "What is the maximum CSV export size?",
      "How long are exported reports retained?",
    ],
  },
  {
    category: "Billing",
    questions: [
      "When are billing invoices sent?",
      "How often does my billing cycle renew?",
      "What happens if a renewal payment fails?",
      "Can I request a refund for an annual plan?",
    ],
  },
  {
    category: "API",
    questions: [
      "What is the API rate limit for the Growth plan?",
      "What is the API rate limit for the Enterprise plan?",
      "What happens when I exceed the API rate limit?",
    ],
  },
];

export default function Home() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [user, setUser] = useState("standard");

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [conversationId, setConversationId] = useState(makeId);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  useEffect(() => {
    fetch(`${API}/api/demo-users`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Could not load demo identities.");
        }
        return response.json();
      })
      .then(setUsers)
      .catch(() =>
        setError(
          "Cannot connect to API. Start the backend and check NEXT_PUBLIC_API_URL."
        )
      );
  }, []);

  function newChat() {
    setMessages([]);
    setQuestion("");
    setError("");
    setFeedback({});
    setConversationId(makeId());
  }

  function selectFaq(q: string) {
    setQuestion(q);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function ask(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const q = question.trim();

    if (q.length < 3 || loading) return;

    setMessages((old) => [
      ...old,
      {
        id: makeId(),
        role: "user",
        content: q,
      },
    ]);

    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API}/api/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Demo-User": user,
        },
        body: JSON.stringify({
          question: q,
          conversation_id: conversationId,
        }),
      });

      const data: AskResponse = await response.json();

      if (!response.ok) {
        throw new Error(
          (data as any).detail || "Request failed."
        );
      }

      setMessages((old) => [
        ...old,
        {
          id: makeId(),
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          mode: data.mode,
          requestId: data.request_id,
          showEvidence: data.show_evidence ?? false,
          showDiagnostics: data.show_diagnostics ?? false,
          status: data.status,
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(
    id: string,
    helpful: boolean
  ) {
    try {
      const response = await fetch(`${API}/api/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Demo-User": user,
        },
        body: JSON.stringify({
          request_id: id,
          helpful,
        }),
      });

      if (!response.ok) {
        throw new Error("Feedback submission failed.");
      }

      setFeedback((old) => ({
        ...old,
        [id]: "Thanks — feedback received.",
      }));
    } catch {
      setFeedback((old) => ({
        ...old,
        [id]: "Feedback could not be sent.",
      }));
    }
  }

  return (
    <main className="shell">
      {/* HEADER */}
      <header className="topbar">
        <div className="brandmark">S</div>

        <div>
          <div className="brand">SOLSTICE LEARNING</div>
          <div className="subbrand">KNOWLEDGE ASSISTANT</div>
        </div>

        <span className="demoTag">HYBRID RAG · V2</span>
      </header>

      {/* HERO */}
      <section className="hero">
        <p className="eyebrow">
          SUPPORT KNOWLEDGE, SIMPLIFIED
        </p>

        <h1>
          What can I help
          <br />
          <span>you find today?</span>
        </h1>

        <p className="intro">
          Ask questions and follow up naturally. Answers are
          grounded in documentation your role is allowed to access.
        </p>
      </section>

      {/* CHAT PANEL */}
      <section className="panel">
        <div className="roleRow">
          <label htmlFor="role">Demo identity</label>

          <select
            id="role"
            value={user}
            onChange={(e) => {
              setUser(e.target.value);
              newChat();
            }}
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.label} · {u.role}
              </option>
            ))}
          </select>

          <button
            type="button"
            className="newChat"
            onClick={newChat}
          >
            ＋ New chat
          </button>
        </div>

        {/* CHAT HISTORY */}
        {messages.length > 0 && (
          <div className="chatHistory" aria-live="polite">
            {messages.map((m) => (
              <div
                className={`message ${m.role}`}
                key={m.id}
              >
                <div className="messageLabel">
                  {m.role === "user"
                    ? "YOU"
                    : "SOLSTICE ASSISTANT"}
                </div>

                <div className="messageBubble">
                  {m.content}
                </div>

                {m.role === "assistant" && (
                  <>
                    {/* SUPPORTING EVIDENCE */}
                    {m.showEvidence &&
                      m.sources &&
                      m.sources.length > 0 && (
                        <div className="sources">
                          <h3>Supporting evidence</h3>

                          {m.sources.slice(0, 1).map((s) => (
                            <article
                              className="source"
                              key={`${m.id}_${s.chunk_id}`}
                            >
                              <div className="sourceTitle">
                                <b>{s.title}</b>

                                <span>
                                  {s.doc_id} · {s.chunk_id} · CITED
                                </span>
                              </div>

                              <p>{s.excerpt}</p>

                              {/* ADMIN / KB MANAGER DIAGNOSTICS */}
                              {m.showDiagnostics && (
                                <details className="diagnostics">
                                  <summary>
                                    View retrieval scores and ranking
                                  </summary>

                                  <div className="scoreGrid">
                                    <div>
                                      <small>
                                        Lexical score (BM25)
                                      </small>
                                      <b>
                                        {fmt(s.lexical_score)}
                                      </b>
                                      <em>
                                        Rank: {s.lexical_rank ?? "—"}
                                      </em>
                                    </div>

                                    <div>
                                      <small>
                                        Semantic similarity
                                      </small>
                                      <b>
                                        {fmt(
                                          s.semantic_similarity
                                        )}
                                      </b>
                                      <em>
                                        Rank:{" "}
                                        {s.semantic_rank ?? "—"}
                                      </em>
                                    </div>

                                    <div>
                                      <small>
                                        Hybrid score (RRF)
                                      </small>
                                      <b>
                                        {fmt(s.hybrid_score)}
                                      </b>
                                      <em>
                                        Final rank: {s.hybrid_rank}
                                      </em>
                                    </div>
                                  </div>
                                </details>
                              )}
                            </article>
                          ))}
                        </div>
                      )}

                    {/* ANSWER STATUS */}
                    <div className="answerMeta">
                      <span>
                        {m.status === "answered"
                          ? "ANSWER WITH EVIDENCE"
                          : "NO SUPPORTED ANSWER"}
                      </span>

                      <span className="mode">
                        {m.mode === "groq"
                          ? "GROQ-GENERATED"
                          : m.mode === "extractive"
                          ? "SOURCE-BASED FALLBACK"
                          : "SAFE ABSTENTION"}
                      </span>
                    </div>

                    {/* FEEDBACK */}
                    {m.requestId && (
                      <div className="feedback">
                        <span>Was this helpful?</span>

                        <button
                          className="feedbackBtn"
                          onClick={() =>
                            sendFeedback(m.requestId!, true)
                          }
                        >
                          Yes
                        </button>

                        <button
                          className="feedbackBtn"
                          onClick={() =>
                            sendFeedback(m.requestId!, false)
                          }
                        >
                          No
                        </button>

                        <small>
                          {feedback[m.requestId] || ""}
                        </small>
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {/* LOADING */}
        {loading && (
          <div className="typing">
            Searching keyword and vector indexes, then preparing
            an evidence-grounded answer…
          </div>
        )}

        {/* QUESTION INPUT */}
        <form onSubmit={ask}>
          <label
            className="questionLabel"
            htmlFor="question"
          >
            YOUR MESSAGE
          </label>

          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              messages.length
                ? "Ask a follow-up, e.g. What about the Enterprise plan?"
                : "Ask a question about your documentation..."
            }
            maxLength={1000}
            rows={3}
          />

          <div className="formBottom">
            <span>{question.length}/1000 characters</span>

            <button
              disabled={
                loading || question.trim().length < 3
              }
            >
              {loading ? "Thinking..." : "Send message  →"}
            </button>
          </div>
        </form>
      </section>

      {/* ERROR */}
      {error && <div className="error">{error}</div>}

      {/* FAQ SECTION */}
      <section className="faqSection">
        <p className="eyebrow">QUICK HELP</p>

        <h2>Frequently Asked Questions</h2>

        <p className="faqIntro">
          Explore common questions about the Solstice platform.
          Select a question to ask the assistant.
        </p>

        {FAQ_GROUPS.map((group) => (
          <div className="faqGroup" key={group.category}>
            <h3>{group.category}</h3>

            {group.questions.map((q) => (
              <button
                type="button"
                className="faqQuestion"
                key={q}
                onClick={() => selectFaq(q)}
              >
                {q}
                <span>↗</span>
              </button>
            ))}
          </div>
        ))}
      </section>

      {/* FOOTER */}
      <footer>
        <span>
          ChromaDB · Sentence Transformers · BM25 · Groq
        </span>

        <span>
          Access-aware · Hybrid retrieval · Evidence-first
        </span>
      </footer>
    </main>
  );
}

import { useMemo, useState } from "react";

type TurnResponse = {
  merge_decision: {
    immediate_response: string;
    deferred_response?: string | null;
    overlay_updates: string[];
  };
};

const API_URL = "http://127.0.0.1:8000/v1/turns";

export function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<TurnResponse | null>(null);

  const canSubmit = useMemo(() => query.trim().length > 0 && !loading, [query, loading]);

  async function askKernel() {
    if (!canSubmit) return;
    setLoading(true);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trigger_type: "user_query",
          user_query: query,
          context: { active_app: "desktop-shell" }
        })
      });
      const data = (await res.json()) as TurnResponse;
      setAnswer(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header>
        <h1>LAWRENCE</h1>
        <p>Parallel-facet assistant kernel preview</p>
      </header>
      <section className="panel">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask LAWRENCE..."
          rows={5}
        />
        <button onClick={askKernel} disabled={!canSubmit}>
          {loading ? "Thinking..." : "Run Turn"}
        </button>
      </section>
      <section className="panel">
        <h2>Immediate</h2>
        <p>{answer?.merge_decision.immediate_response ?? "No response yet."}</p>
        <h2>Deferred</h2>
        <p>{answer?.merge_decision.deferred_response ?? "No deferred output."}</p>
        <h2>Overlay Updates</h2>
        <ul>
          {(answer?.merge_decision.overlay_updates ?? []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

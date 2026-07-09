import { useEffect, useState } from "react";

export default function App() {
  const [suggestion, setSuggestion] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8765/ws");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "suggestion") {
        setSuggestion(data.reason);
      }
    };
    return () => ws.close();
  }, []);

  return (
    <div className="app">
      {suggestion && (
        <div className="suggestion-banner">
          <p>{suggestion}</p>
          <button>Automatiser</button>
          <button>Ignorer</button>
        </div>
      )}
    </div>
  );
}

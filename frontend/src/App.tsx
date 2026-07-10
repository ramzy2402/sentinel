declare module "react";
import * as React from "react";

export default function App() {
  const [suggestion, setSuggestion] = React.useState<string | null>(null);

  React.useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8765/ws");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "suggestion") {
        setSuggestion(data.reason);
      }
    };
    return () => ws.close();
  }, []);

  return React.createElement(
    "div",
    { className: "app" },
    suggestion &&
      React.createElement(
        "div",
        { className: "suggestion-banner" },
        React.createElement("p", null, suggestion),
        React.createElement("button", null, "Automatiser"),
        React.createElement("button", null, "Ignorer")
      )
  );
}

export function DebugDrawer() {
  return (
    <details className="debug-drawer">
      <summary>Integration notes</summary>
      <p>Mock and real API clients share the same TypeScript interface. Set VITE_API_CLIENT=real and VITE_API_BASE_URL to switch.</p>
    </details>
  );
}

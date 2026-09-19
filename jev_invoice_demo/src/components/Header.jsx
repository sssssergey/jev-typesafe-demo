export default function Header({ runStatus, hasKey, simulate, theme, onToggleTheme, onStart, onTogglePause }) {
  const live = hasKey && !simulate;
  const canPause = runStatus === "running" || runStatus === "paused";
  return (
    <header className="top">
      <div className="brand">
        <h1>
          <span>Jev</span>.TypeSafe
        </h1>
        <p>Invoice validation — amount match and scope coverage</p>
      </div>
      <div className="controls">
        <span className={`pill ${live ? "ok" : "warn"}`}>{live ? "live Jev key" : "local preview"}</span>
        <span className="pill">{runStatus}</span>
        <button className="btn primary" type="button" onClick={onStart}>
          Start
        </button>
        <button className="btn" type="button" onClick={onTogglePause} disabled={!canPause}>
          {runStatus === "paused" ? "Resume" : "Pause"}
        </button>
        <button
          className="btn icon"
          type="button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? "☀" : "☽"}
        </button>
      </div>
    </header>
  );
}

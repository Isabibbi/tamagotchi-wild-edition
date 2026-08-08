"""Tema della dashboard web del CRAS."""

NICEGUI_CSS = """
:root {
  --cras-ink: #0f172a;
  --cras-muted: #64748b;
  --cras-line: #e2e8f0;
  --cras-green: #15803d;
}
body {
  background:
    radial-gradient(circle at 8% 4%, rgba(34, 197, 94, .13), transparent 28rem),
    radial-gradient(circle at 92% 12%, rgba(37, 99, 235, .10), transparent 25rem),
    #f1f5f9;
  color: var(--cras-ink);
}
.nicegui-content {
  max-width: 1680px;
  margin: 0 auto;
  padding: 1.25rem;
}
.cras-card {
  border: 1px solid rgba(226, 232, 240, .9);
  border-radius: 1.25rem;
  background: rgba(255, 255, 255, .92);
  box-shadow: 0 16px 45px rgba(15, 23, 42, .07);
  backdrop-filter: blur(12px);
}
.metric-card {
  min-height: 7.3rem;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  background: linear-gradient(145deg, #ffffff, #f8fafc);
  box-shadow: 0 8px 28px rgba(15, 23, 42, .05);
}
.grid-shell svg {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 1rem;
  filter: drop-shadow(0 12px 22px rgba(15, 23, 42, .09));
}
.grid-shell,
.event-log {
  min-width: 0;
}
.staff-roster {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: .65rem;
}
.staff-chip {
  display: flex;
  align-items: center;
  gap: .65rem;
  padding: .65rem .75rem;
  border: 1px solid #e2e8f0;
  border-radius: .85rem;
  background: #f8fafc;
}
.staff-chip.staff-active {
  border-color: #facc15;
  background: #fffbeb;
}
.staff-dot {
  display: grid;
  place-items: center;
  min-width: 2rem;
  height: 2rem;
  border-radius: 999px;
  color: white;
  font-weight: 800;
  box-shadow: 0 3px 10px rgba(15, 23, 42, .18);
}
.staff-chip span:last-child { display: flex; flex-direction: column; }
.staff-chip strong { color: #0f172a; font-size: .78rem; }
.staff-chip small { color: #64748b; font-size: .67rem; }
.room-access-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .65rem;
}
.room-access {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .5rem;
  padding: .72rem .8rem;
  border-radius: .85rem;
  border: 1px solid #dbeafe;
  background: #eff6ff;
}
.room-access.room-full { border-color: #fed7aa; background: #fff7ed; }
.room-access span { display: flex; flex-direction: column; min-width: 0; }
.room-access strong { color: #1e293b; font-size: .75rem; }
.room-access small {
  color: #64748b;
  font-size: .65rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.room-access b { color: #0f172a; font-size: 1rem; }
.event-log {
  background: #07111f !important;
  border: 1px solid #1e293b;
  border-radius: 1rem;
  color: #dbeafe;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: .76rem;
  line-height: 1.55;
}
@media (max-width: 900px) {
  .nicegui-content { padding: .75rem; }
  .room-access-grid { grid-template-columns: 1fr; }
}
"""

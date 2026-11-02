import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight, Clock3, FolderOpen, Layers3, MessageSquare, ShieldCheck } from "lucide-react";
import { api,fetchJSON, type PaginatedSessions, type StatusResponse } from "@/lib/api";

import { CityHero } from "@/components/CityHero";

export default function HomePage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [sessions, setSessions] = useState<PaginatedSessions | null>(null);
  const [connection,setConnection]=useState<{connected:boolean;connection_kind?:string}|null>(null);

  useEffect(() => {
    let active = true;
    void api.getStatus().then(value => { if (active) setStatus(value); }).catch(() => {});
    void fetchJSON<{connected:boolean;connection_kind?:string}>("/api/indra/server-status").then(value=>{if(active)setConnection(value);}).catch(()=>{});
    void api.getSessions(3, 0, undefined, "recent").then(value => { if (active) setSessions(value); }).catch(() => {});
    return () => { active = false; };
  }, []);

  return (
    <main className="indra-home">
      <CityHero />
      <div className="indra-home-grid">
        <section className="indra-home-panel" aria-labelledby="recent-heading">
          <div className="indra-home-section-heading"><div><span>CONTINUE YOUR WORK</span><h2 id="recent-heading">Recent tasks</h2></div><Link to="/sessions">View all <ArrowUpRight size={16} /></Link></div>
          {sessions?.sessions.length ? <div className="indra-home-task-list">{sessions.sessions.map(session => <Link key={session.id} to={`/chat?resume=${encodeURIComponent(session.id)}`} className="indra-home-task"><span className="indra-home-task-icon"><MessageSquare size={20} /></span><span><strong translate={session.title || session.preview ? "no" : undefined}>{session.title || session.preview || "Untitled session"}</strong><small>{session.model || "Model unavailable"} · {session.message_count} messages</small></span><ArrowUpRight size={18} /></Link>)}</div> : <div className="indra-home-empty"><Clock3 size={22} /><p>{sessions ? "No recent tasks yet. Start with a request above." : "Recent tasks unavailable."}</p></div>}
        </section>
        <section className="indra-home-panel indra-home-runtime" aria-labelledby="runtime-heading">
          <div className="indra-home-section-heading"><div><span>WORKSPACE HEALTH</span><h2 id="runtime-heading">Runtime</h2></div><Link to="/system">Details <ArrowUpRight size={16} /></Link></div>
          <div className="indra-home-runtime-state"><span className={connection?.connected ? "indra-home-status-dot ready" : "indra-home-status-dot"} /><strong>{connection ? (connection.connected ? connection.connection_kind==="cloud"?"Provider configured":"Ready to work" : "Check model connection") : "Checking model connection…"}</strong></div>
          <p>{connection?.connected ? "Your selected model is configured for new tasks. Availability is checked on each request." : "Open runtime details for connection and service information."}</p>
          <div className="indra-home-runtime-meta"><span>Active sessions</span><strong>{status ? status.active_sessions : "—"}</strong></div>
        </section>
      </div>
      <div className="indra-home-links"><Link to="/files"><FolderOpen size={19} /> Knowledge <ArrowUpRight size={16} /></Link><Link to="/models"><Layers3 size={19} /> Models <ArrowUpRight size={16} /></Link><Link to="/logs"><ShieldCheck size={19} /> Audit <ArrowUpRight size={16} /></Link></div>
    </main>
  );
}

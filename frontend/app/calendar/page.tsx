"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertCircle, CalendarDays, Clock3, Loader2, MapPin, RefreshCw, Sparkles, Users } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";

export default function CalendarPage() {
  const [data, setData] = useState<any>(null); const [loading, setLoading] = useState(true);
  const load = async () => { setLoading(true); try { setData(await api.getTodayCalendar()); } catch (error: any) { setData({ is_connected: false, events: [], sync_error: error.message || "Calendar could not be loaded." }); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

  return <AppShell title="Calendar" description="Your day, with room left to think.">
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex items-end justify-between"><div><p className="eyebrow text-[#00846F]">{today}</p><h2 className="mt-1 text-[19px] font-semibold tracking-tight text-[#1B1B2F]">Today</h2></div>{data?.is_connected && <button onClick={load} disabled={loading} className="btn-secondary"><RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />Refresh</button>}</div>
      {loading ? <div className="grid min-h-64 place-items-center"><Loader2 className="h-5 w-5 animate-spin text-[#9291A5]" /></div> : data?.sync_error ? <section className="surface-flat flex items-start gap-4 p-6"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#FFF4E0] text-[#9A6500]"><AlertCircle className="h-5 w-5" /></span><div><h3 className="text-sm font-semibold text-[#1B1B2F]">Calendar needs attention</h3><p className="mt-1 max-w-2xl text-[11px] leading-5 text-[#6B6B80]">{data.sync_error}</p><Link href="/integrations" className="mt-4 inline-flex text-[11px] font-semibold text-[#00846F]">Reconnect Calendar →</Link></div></section> : !data?.is_connected ? <EmptyState icon={CalendarDays} title="Connect your calendar" description="See meetings and focus windows in one calm day view." action={<Link href="/integrations" className="btn-primary">Connect Google Calendar</Link>} /> : data.events.length === 0 ? <EmptyState icon={CalendarDays} title="Your day is open" description="Google Calendar is synchronized and no events were found for today." /> : <section className="surface-flat overflow-hidden p-4 sm:p-6">
        <div className="mb-4 flex items-center justify-between border-b border-[#F0F0F7] pb-4"><div><p className="text-[12px] font-semibold text-[#1B1B2F]">{data.events.length} scheduled {data.events.length === 1 ? "event" : "events"}</p><p className="mt-0.5 text-[10px] text-[#6B6B80]">{data.account_email || "Connected calendar"}</p></div><span className="rounded-full bg-[#E3FBF7] px-2.5 py-1 text-[9px] font-semibold text-[#00846F]">Calendar live</span></div>
        <div className="space-y-3">{data.events.map((event: any, index: number) => { const start = new Date(event.start); const end = new Date(event.end); return <div key={event.id}>
          {index === 1 && <div className="mb-3 grid grid-cols-[62px_1fr] gap-3"><span /><Link href={`/assistant?prompt=${encodeURIComponent(`Prepare me for ${event.summary}`)}`} className="interactive-card flex items-center gap-3 rounded-[13px] bg-[#EEEDFE] px-4 py-3 text-[#4C3FBF]"><Sparkles className="h-4 w-4 shrink-0" /><div><p className="text-[10px] font-semibold uppercase tracking-wide">Assistant insight</p><p className="mt-0.5 text-[11px]">Meeting prep is one ask away.</p></div></Link></div>}
          <article className="grid grid-cols-[62px_1fr] gap-3"><div className="pt-3 text-right"><p className="mono text-[10px] font-semibold text-[#1B1B2F]">{start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p><p className="mono mt-1 text-[8px] text-[#9291A5]">{Math.max(0, Math.round((end.getTime() - start.getTime()) / 60000))}m</p></div><div className="interactive-card rounded-[13px] border border-[#00C2A8]/20 bg-[#E3FBF7] px-4 py-3.5"><h3 className="text-[13px] font-semibold text-[#1B1B2F]">{event.summary}</h3>{event.description && <p className="mt-1 line-clamp-2 text-[10px] leading-5 text-[#00846F]">{event.description}</p>}<div className="mono mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[8px] text-[#00846F]">{event.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{event.location}</span>}{event.attendees?.length > 0 && <span className="flex items-center gap-1"><Users className="h-3 w-3" />{event.attendees.length} people</span>}<span className="flex items-center gap-1"><Clock3 className="h-3 w-3" />{end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div></div></article>
        </div>; })}</div>
      </section>}
    </div>
  </AppShell>;
}

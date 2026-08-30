"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CalendarDays, Check, CheckSquare2, CircleDot, Github, Inbox, Loader2, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const statStyles = {
  inbox: { tint: "bg-[#FFEAE8]", color: "text-[#C4392E]", icon: Inbox },
  calendar: { tint: "bg-[#E3FBF7]", color: "text-[#00846F]", icon: CalendarDays },
  tasks: { tint: "bg-[#FFF4E0]", color: "text-[#9A6500]", icon: CheckSquare2 },
  github: { tint: "bg-[#EEEDFE]", color: "text-[#4C3FBF]", icon: Github },
};

export default function DashboardPage() {
  const router = useRouter(); const { user, isLoading } = useAuth();
  const [tasks, setTasks] = useState<any[]>([]); const [inbox, setInbox] = useState<any>(null); const [calendar, setCalendar] = useState<any>(null); const [integrations, setIntegrations] = useState<any[]>([]); const [loading, setLoading] = useState(true);
  useEffect(() => { if (!isLoading && !user) router.replace("/login"); else if (user) Promise.all([api.getTasks().catch(() => []), api.getInbox().catch(() => null), api.getTodayCalendar().catch(() => null), api.getIntegrations().catch(() => [])]).then(([taskData, inboxData, calendarData, integrationData]) => { setTasks(taskData); setInbox(inboxData); setCalendar(calendarData); setIntegrations(integrationData); }).finally(() => setLoading(false)); }, [user, isLoading]);

  const openTasks = useMemo(() => tasks.filter(task => !["completed", "cancelled"].includes(task.status)), [tasks]);
  const priority = useMemo(() => [...openTasks].sort((a, b) => ({ urgent: 4, high: 3, medium: 2, low: 1 }[b.priority as "urgent"] || 0) - ({ urgent: 4, high: 3, medium: 2, low: 1 }[a.priority as "urgent"] || 0))[0], [openTasks]);
  const githubConnected = integrations.some(item => item.id === "github" && item.status === "connected");
  const activity = useMemo(() => {
    const rows = [
      ...(inbox?.emails || []).slice(0, 2).map((item: any) => ({ type: "inbox", text: item.subject, note: item.sender, time: item.date, href: "/inbox" })),
      ...openTasks.slice(0, 2).map((item: any) => ({ type: "tasks", text: item.title, note: `${item.priority} priority`, time: item.due_date ? `Due ${new Date(item.due_date).toLocaleDateString()}` : "Open", href: "/tasks" })),
      ...(calendar?.events || []).slice(0, 2).map((item: any) => ({ type: "calendar", text: item.summary, note: "Calendar", time: new Date(item.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), href: "/calendar" })),
    ];
    return rows.slice(0, 6);
  }, [inbox, openTasks, calendar]);

  if (isLoading || !user) return <div className="grid min-h-screen place-items-center bg-[#F7F7FC] text-[#6B6B80]"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  const firstName = (user.full_name || "there").split(" ")[0];
  const greeting = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 18 ? "Good afternoon" : "Good evening";
  const stats = [
    { key: "inbox", label: "Inbox", value: inbox?.action_needed_count ?? 0, note: `${inbox?.urgent_count || 0} urgent` },
    { key: "calendar", label: "Events", value: calendar?.events?.length || 0, note: "today" },
    { key: "tasks", label: "Tasks", value: openTasks.length, note: "open" },
    { key: "github", label: "Open PRs", value: githubConnected ? "Live" : "—", note: githubConnected ? "ask Northstar" : "connect GitHub" },
  ] as const;

  return <AppShell title={`${greeting}, ${firstName}`} description="What matters is already within reach." commandMode="full">
    <div className="space-y-5">
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(item => { const style = statStyles[item.key]; const Icon = style.icon; return <Link href={item.key === "inbox" ? "/inbox" : item.key === "calendar" ? "/calendar" : item.key === "tasks" ? "/tasks" : "/integrations"} key={item.key} className={`interactive-card flex items-center gap-3 rounded-[14px] p-4 ${style.tint}`}><span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/70 ${style.color}`}><Icon className="h-[17px] w-[17px]" /></span><div className="min-w-0"><p className={`font-[Sora] text-xl font-semibold ${style.color}`}>{loading ? "·" : item.value}</p><p className="text-[11px] font-semibold text-[#1B1B2F]">{item.label}</p><p className={`truncate text-[9px] ${style.color} opacity-75`}>{item.note}</p></div></Link>; })}
      </section>

      <section className="grid gap-5 lg:grid-cols-[.72fr_1.28fr]">
        <div className="surface interactive-card p-5 sm:p-6">
          <div className="flex items-center justify-between"><div><p className="eyebrow">Northstar focus</p><h2 className="mt-1 text-[17px] font-semibold text-[#1B1B2F]">One thing at a time</h2></div><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#EEEDFE] text-[#6C5CE7]"><Sparkles className="h-4 w-4" /></span></div>
          {priority ? <div className="mt-7"><span className={`rounded-full px-2.5 py-1 text-[9px] font-semibold uppercase tracking-wide ${priority.priority === "urgent" ? "bg-[#FFEAE8] text-[#C4392E]" : "bg-[#FFF4E0] text-[#9A6500]"}`}>{priority.priority} priority</span><h3 className="mt-4 text-[18px] font-semibold leading-7 text-[#1B1B2F]">{priority.title}</h3><p className="mt-2 line-clamp-2 text-[12px] leading-5 text-[#6B6B80]">{priority.description || "Give this one uninterrupted focus block and move it forward."}</p><Link href="/tasks" className="mt-6 inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#6C5CE7]">Open task <ArrowRight className="h-3.5 w-3.5" /></Link></div> : <div className="mt-8 rounded-[14px] bg-[#E3FBF7] p-5"><Check className="h-5 w-5 text-[#00846F]" /><p className="mt-3 text-sm font-semibold text-[#1B1B2F]">Your queue is clear.</p><p className="mt-1 text-[11px] leading-5 text-[#00846F]">Nothing is competing for your attention right now.</p></div>}
        </div>

        <div className="surface-flat overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#F0F0F7] px-5 py-4"><div><p className="eyebrow">Recent activity</p><h2 className="mt-1 text-[15px] font-semibold text-[#1B1B2F]">Across your workspace</h2></div><CircleDot className="h-4 w-4 text-[#9291A5]" /></div>
          <div className="divide-y divide-[#F0F0F7]">{activity.map((item: any, index) => { const color = item.type === "inbox" ? "bg-[#FF6B5E]" : item.type === "calendar" ? "bg-[#00C2A8]" : "bg-[#FFB020]"; return <Link href={item.href} key={`${item.type}-${index}`} className="group grid grid-cols-[12px_1fr_auto] items-center gap-3 px-5 py-3.5 transition hover:bg-[#FAFAFE]"><span className={`h-2 w-2 rounded-full ${color}`} /><div className="min-w-0"><p className="truncate text-[12px] font-medium text-[#1B1B2F]">{item.text}</p><p className="mt-0.5 truncate text-[10px] text-[#6B6B80]">{item.note}</p></div><span className="mono text-[9px] text-[#9291A5]">{item.time}</span></Link>; })}{!loading && activity.length === 0 && <div className="px-5 py-12 text-center"><p className="text-xs font-medium text-[#6B6B80]">No activity yet</p><p className="mt-1 text-[10px] text-[#9291A5]">Connect a tool or add your first task.</p></div>}</div>
        </div>
      </section>
    </div>
  </AppShell>;
}

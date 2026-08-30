"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell, Check, Loader2, Mail, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";

export default function NotificationsPage() {
  const [items, setItems] = useState<any[]>([]); const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); api.getNotifications().then(setItems).finally(() => setLoading(false)); }; useEffect(load, []);
  const mark = async (id: string) => { await api.markNotificationRead(id); setItems(items.map(item => item.id === id ? { ...item, is_read: true } : item)); };
  const markAll = async () => { await api.markAllNotificationsRead(); setItems(items.map(item => ({ ...item, is_read: true }))); };
  const unread = items.filter(item => !item.is_read).length;
  return <AppShell title="Notifications" description="Only the signals that need your attention."><div className="space-y-6"><div className="flex items-end justify-between"><div><p className="eyebrow">Activity</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">{unread ? `${unread} unread` : "You’re up to date"}</h2></div>{unread > 0 && <button onClick={markAll} className="btn-secondary">Mark all read</button>}</div>
    {loading ? <div className="grid min-h-64 place-items-center"><Loader2 className="h-5 w-5 animate-spin text-[#9291A5]" /></div> : items.length === 0 ? <EmptyState icon={Bell} title="No notifications" description="Important updates will appear here when your connected tools or task deadlines need attention." /> : <div className="surface-flat divide-y divide-[#F0F0F7] overflow-hidden">{items.map(item => <article key={item.id} className={`flex gap-4 p-5 sm:p-6 ${item.is_read ? "bg-white" : "bg-[#EEEDFE]/40"}`}><div className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${item.severity === "urgent" ? "bg-[#FFEAE8] text-[#C4392E]" : "bg-[#F0F0F7] text-[#6B6B80]"}`}>{item.category === "email" ? <Mail className="h-4 w-4" /> : <TriangleAlert className="h-4 w-4" />}</div><div className="min-w-0 flex-1"><div className="flex items-center gap-2">{item.source_link ? <Link href={item.source_link} className="text-sm font-semibold text-[#1B1B2F] hover:text-[#4C3FBF]">{item.title}</Link> : <h3 className="text-sm font-semibold text-[#1B1B2F]">{item.title}</h3>}{!item.is_read && <span className="beacon h-1.5 w-1.5 rounded-full bg-[#FF6B5E]" />}</div><p className="mt-1 text-xs leading-5 text-[#6B6B80]">{item.message}</p><p className="mono mt-2 text-[9px] text-[#9291A5]">{new Date(item.created_at).toLocaleString()}</p></div>{!item.is_read && <button onClick={() => mark(item.id)} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-[#9291A5] hover:bg-white hover:text-[#6C5CE7]" aria-label="Mark as read"><Check className="h-4 w-4" /></button>}</article>)}</div>}
  </div></AppShell>;
}

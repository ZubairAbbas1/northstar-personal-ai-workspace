"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CommandBar } from "@/components/CommandBar";

export function Header({ title, description, mode }: { title: string; description?: string; mode: "slim" | "full" }) {
  const [unread, setUnread] = useState(0);
  useEffect(() => { api.getNotifications().then(items => setUnread(items.filter((item: any) => !item.is_read).length)).catch(() => {}); }, []);
  if (mode === "full") return <header className="border-b border-[#E4E3F5]/80 bg-[#F7F7FC] px-4 pb-1 pt-6 sm:px-6 md:px-8"><div className="mx-auto max-w-[1180px]"><div className="mb-4 flex items-start justify-between gap-4"><div><p className="eyebrow">Command deck</p><h1 className="mt-1 text-[20px] font-semibold tracking-[-.025em] text-[#1B1B2F]">{title}</h1>{description && <p className="mt-1 text-[12px] text-[#6B6B80]">{description}</p>}</div><NotificationButton unread={unread} /></div><CommandBar /></div></header>;
  return <header className="sticky top-0 z-30 border-b border-[#E4E3F5]/80 bg-[#F7F7FC]/95 px-4 py-3 backdrop-blur-xl sm:px-6 md:px-8"><div className="mx-auto flex max-w-[1180px] items-center gap-3"><div className="hidden min-w-[150px] lg:block"><h1 className="truncate text-[15px] font-semibold tracking-tight text-[#1B1B2F]">{title}</h1>{description && <p className="truncate text-[10px] text-[#6B6B80]">{description}</p>}</div><CommandBar compact /><NotificationButton unread={unread} /></div></header>;
}

function NotificationButton({ unread }: { unread: number }) { return <Link href="/notifications" className="relative grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-[#E4E3F5] bg-white text-[#6B6B80] transition hover:-translate-y-0.5 hover:text-[#1B1B2F]" aria-label="Notifications"><Bell className="h-4 w-4" />{unread > 0 && <span className="beacon absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[#FF6B5E] ring-2 ring-white" />}</Link>; }

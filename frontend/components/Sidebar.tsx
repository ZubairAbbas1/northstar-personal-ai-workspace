"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, CheckSquare2, Github, Inbox, LayoutDashboard, LogOut, Settings, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const items = [
  { name: "Overview", href: "/", icon: LayoutDashboard, active: "bg-white/12 text-white" },
  { name: "Inbox", href: "/inbox", icon: Inbox, active: "bg-[#FF6B5E] text-white" },
  { name: "Tasks", href: "/tasks", icon: CheckSquare2, active: "bg-[#FFB020] text-[#1B1B2F]" },
  { name: "Calendar", href: "/calendar", icon: CalendarDays, active: "bg-[#00C2A8] text-[#1B1B2F]" },
  { name: "GitHub & tools", href: "/integrations", icon: Github, active: "bg-white text-[#1B1B2F]" },
  { name: "Assistant", href: "/assistant", icon: Sparkles, active: "bg-[#6C5CE7] text-white" },
];

function NavLink({ item, pathname }: { item: typeof items[number]; pathname: string }) {
  const active = pathname === item.href;
  const Icon = item.icon;
  return <Link href={item.href} aria-label={item.name} title={item.name} className={cn("group relative grid h-9 w-9 place-items-center rounded-[11px] text-[#9291B5] transition duration-150 hover:bg-white/10 hover:text-white", active && item.active)}><Icon className="h-[17px] w-[17px]" /><span className="pointer-events-none absolute left-12 z-[70] hidden whitespace-nowrap rounded-lg bg-[#1B1B2F] px-2.5 py-1.5 text-[10px] font-medium text-white opacity-0 shadow-lg transition group-hover:opacity-100 md:block">{item.name}</span></Link>;
}

export function Sidebar() {
  const pathname = usePathname(); const { user, logout } = useAuth();
  return <>
    <aside className="fixed inset-y-0 left-0 z-50 hidden w-[52px] flex-col items-center border-r border-white/5 bg-[#1B1B2F] py-3 md:flex">
      <Link href="/" aria-label="Northstar home" title="Northstar" className="mb-7 grid h-9 w-9 place-items-center rounded-xl bg-[#6C5CE7] text-white shadow-[0_0_22px_rgba(108,92,231,.28)]"><Sparkles className="h-[17px] w-[17px]" /></Link>
      <nav className="flex flex-col items-center gap-2">{items.map(item => <NavLink key={item.href} item={item} pathname={pathname} />)}</nav>
      <div className="mt-auto flex flex-col items-center gap-2">
        <Link href="/settings" aria-label="Settings" title="Settings" className={cn("grid h-9 w-9 place-items-center rounded-[11px] text-[#9291B5] transition hover:bg-white/10 hover:text-white", pathname === "/settings" && "bg-[#6C5CE7] text-white")}><Settings className="h-[17px] w-[17px]" /></Link>
        <button onClick={logout} aria-label="Sign out" title="Sign out" className="grid h-9 w-9 place-items-center rounded-[11px] text-[#9291B5] transition hover:bg-[#FF6B5E]/20 hover:text-[#FF8B82]"><LogOut className="h-[16px] w-[16px]" /></button>
        <div title={user?.email || "Your account"} className="mono grid h-7 w-7 place-items-center rounded-full bg-white/10 text-[9px] font-semibold text-white">{(user?.full_name || user?.email || "U")[0].toUpperCase()}</div>
      </div>
    </aside>

    <nav className="fixed inset-x-0 bottom-0 z-50 flex h-[60px] items-center justify-around border-t border-[#E4E3F5] bg-[#1B1B2F]/[.98] px-2 backdrop-blur-xl md:hidden">
      {items.slice(0, 4).map(item => { const active = pathname === item.href; const Icon = item.icon; return <Link key={item.href} href={item.href} aria-label={item.name} className={cn("grid h-10 w-10 place-items-center rounded-xl text-[#9291B5] transition", active && item.active)}><Icon className="h-[18px] w-[18px]" /></Link>; })}
      <Link href="/assistant" aria-label="Assistant" className={cn("grid h-10 w-10 place-items-center rounded-xl text-[#9291B5]", pathname === "/assistant" ? "bg-[#6C5CE7] text-white" : "") }><Sparkles className="h-[18px] w-[18px]" /></Link>
      <Link href="/settings" aria-label="Settings" className={cn("grid h-10 w-10 place-items-center rounded-xl text-[#9291B5]", pathname === "/settings" ? "bg-[#6C5CE7] text-white" : "") }><Settings className="h-[18px] w-[18px]" /></Link>
    </nav>
  </>;
}

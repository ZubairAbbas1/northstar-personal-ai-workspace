"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckSquare2, FolderKanban, Loader2, Search, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";

const icons: any = { Task: CheckSquare2, Project: FolderKanban, Memory: Sparkles };
const destinations: Record<string, string> = { Task: "/tasks", Project: "/projects", Memory: "/settings?tab=memory" };
export default function SearchPage() {
  const [query, setQuery] = useState(""); const [result, setResult] = useState<any>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const search = async (event: React.FormEvent) => { event.preventDefault(); if (query.trim().length < 2) return; setLoading(true); setError(""); try { setResult(await api.search(query.trim())); } catch (err: any) { setError(err.message || "Search failed"); } finally { setLoading(false); } };
  return <AppShell title="Search" description="Find tasks, projects, and saved context in your private workspace."><div className="mx-auto max-w-3xl space-y-7"><div><p className="eyebrow">Workspace search</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Find the context you need</h2></div><form onSubmit={search} className="surface flex items-center gap-3 p-2"><Search className="ml-2 h-5 w-5 shrink-0 text-slate-400" /><input className="min-w-0 flex-1 border-0 bg-transparent px-1 py-2.5 text-sm outline-none placeholder:text-slate-400" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tasks, projects, and memory…" /><button className="btn-primary" disabled={loading || query.trim().length < 2}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}</button></form>{error && <p className="rounded-xl bg-red-50 px-4 py-3 text-xs text-red-700">{error}</p>}
    {result && (result.total === 0 ? <EmptyState icon={Search} title="No matches found" description={`Nothing in your workspace matched “${result.query}”. Try a shorter or more specific phrase.`} /> : <div><p className="mb-3 text-xs text-slate-500">{result.total} {result.total === 1 ? "result" : "results"}</p><div className="surface-flat divide-y divide-slate-100 overflow-hidden">{result.results.map((item: any) => { const Icon = icons[item.domain] || Search; return <Link href={destinations[item.domain] || "/"} key={`${item.domain}-${item.id}`} className="flex gap-4 p-5 transition hover:bg-slate-50"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500"><Icon className="h-4 w-4" /></div><div className="min-w-0"><div className="flex items-center gap-2"><h3 className="truncate text-sm font-semibold text-slate-900">{item.title}</h3><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-500">{item.domain}</span></div><p className="mt-1 text-xs leading-5 text-slate-500">{item.snippet}</p></div></Link>; })}</div></div>)}
  </div></AppShell>;
}

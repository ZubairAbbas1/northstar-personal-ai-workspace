import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";

export function AppShell({ title, description, children, commandMode = "slim" }: { title: string; description?: string; children: React.ReactNode; commandMode?: "slim" | "full" }) {
  return <div className="min-h-screen bg-[#F7F7FC]"><Sidebar /><div className="min-w-0 md:ml-[52px]"><Header title={title} description={description} mode={commandMode} /><main className="page-wrap page-enter">{children}</main></div></div>;
}

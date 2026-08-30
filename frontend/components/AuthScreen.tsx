"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, ArrowRight, Compass, Eye, EyeOff, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function AuthScreen({ mode }: { mode: "login" | "register" }) {
  const router = useRouter(); const { login } = useAuth();
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false); const [leaving, setLeaving] = useState(false);
  const isRegister = mode === "register";

  useEffect(() => { setSessionExpired(new URLSearchParams(window.location.search).get("reason") === "session_expired"); }, []);
  const complete = (res: any) => { login(res.access_token, res.user); setLeaving(true); window.setTimeout(() => router.push(res.user?.has_completed_onboarding ? "/" : "/onboarding"), 180); };
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); setError(""); try { complete(isRegister ? await api.register({ email: email.trim(), password, full_name: name.trim() }) : await api.login({ email: email.trim(), password })); } catch (err: any) { setError(err.message || "We couldn't complete that request."); setBusy(false); } };

  return <main className={`min-h-screen bg-[#F7F7FC] p-3 transition-opacity duration-200 sm:p-5 ${leaving ? "opacity-0" : "opacity-100"}`}>
    <div className="mx-auto grid min-h-[calc(100vh-1.5rem)] max-w-6xl overflow-hidden rounded-[22px] border border-[#E4E3F5] bg-white sm:min-h-[calc(100vh-2.5rem)] lg:grid-cols-2">
      <section className="flex items-center justify-center px-6 py-10 sm:px-12 lg:px-16">
        <div className="w-full max-w-[380px]">
          <div className="mb-12 flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-[13px] bg-[#6C5CE7] text-white shadow-[0_8px_22px_rgba(108,92,231,.2)]"><Sparkles className="h-[18px] w-[18px]" /></span><div><p className="font-[Sora] text-sm font-semibold text-[#1B1B2F]">Northstar</p><p className="text-[10px] text-[#6B6B80]">Personal AI workspace</p></div></div>
          <p className="eyebrow text-[#6C5CE7]">{isRegister ? "Create your command deck" : "Welcome back"}</p>
          <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-[-.035em] text-[#1B1B2F]">{isRegister ? "Find your focus." : "Pick up where you left off."}</h1>
          <p className="mt-3 max-w-sm text-[13px] leading-6 text-[#6B6B80]">{isRegister ? "A private place for the work, messages, meetings, and context that matter." : "Your priorities, conversations, schedule, and assistant are ready when you are."}</p>

          {!isRegister && sessionExpired && <div className="mt-5 flex items-start gap-2 rounded-xl border border-[#FFB020]/30 bg-[#FFF4E0] px-3.5 py-3 text-xs leading-5 text-[#9A6500]"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>Your session expired. Sign in again to continue securely.</span></div>}

          <form onSubmit={submit} className="mt-8 space-y-4">
            {isRegister && <div><label className="mb-1.5 block text-[11px] font-semibold text-[#1B1B2F]">Full name</label><input className="field" value={name} onChange={event => setName(event.target.value)} placeholder="Your name" required /></div>}
            <div><label className="mb-1.5 block text-[11px] font-semibold text-[#1B1B2F]">Email address</label><input className="field" type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@company.com" autoComplete="email" required /></div>
            <div><div className="mb-1.5 flex items-center justify-between"><label className="text-[11px] font-semibold text-[#1B1B2F]">Password</label><span className="text-[10px] text-[#9291A5]">8+ characters</span></div><div className="relative"><input className="field pr-11" type={showPassword ? "text" : "password"} value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter your password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={8} required /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9291A5] transition hover:text-[#1B1B2F]" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></div>
            {error && <div className="rounded-xl border border-[#FF6B5E]/25 bg-[#FFEAE8] px-3.5 py-3 text-xs leading-5 text-[#C4392E]">{error}</div>}
            <button className="btn-primary h-11 w-full" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>{isRegister ? "Create workspace" : "Sign in"}<ArrowRight className="h-4 w-4" /></>}</button>
          </form>
          <p className="mt-7 text-center text-xs text-[#6B6B80]">{isRegister ? "Already have an account?" : "New to Northstar?"} <Link href={isRegister ? "/login" : "/register"} className="font-semibold text-[#6C5CE7] hover:text-[#4C3FBF]">{isRegister ? "Sign in" : "Create an account"}</Link></p>
        </div>
      </section>

      <section className="relative hidden overflow-hidden bg-[#1B1B2F] lg:block" aria-label="Northstar visual">
        <div className="orb-one absolute left-[10%] top-[12%] h-72 w-72 rounded-full bg-[#6C5CE7]/45 blur-[88px]" />
        <div className="orb-two absolute -right-20 top-[32%] h-64 w-64 rounded-full bg-[#FF6B5E]/35 blur-[86px]" />
        <div className="orb-three absolute bottom-[5%] left-[22%] h-72 w-72 rounded-full bg-[#00C2A8]/30 blur-[90px]" />
        <div className="orb-two absolute bottom-[18%] right-[12%] h-44 w-44 rounded-full bg-[#FFB020]/25 blur-[70px]" />
        <div className="absolute inset-0 opacity-[.08]" style={{ backgroundImage: "radial-gradient(circle at center, #fff 1px, transparent 1px)", backgroundSize: "30px 30px" }} />
        <div className="absolute inset-0 flex flex-col items-center justify-center px-12 text-center">
          <div className="star-breathe grid h-24 w-24 place-items-center rounded-[30px] border border-white/15 bg-white/10 text-white backdrop-blur-xl"><Compass className="h-10 w-10" strokeWidth={1.4} /></div>
          <p className="mt-8 font-[Sora] text-xl font-semibold text-white">Quietly pointing you forward.</p>
          <p className="mt-3 max-w-sm text-[13px] leading-6 text-[#B8B7D0]">One calm command deck for everything competing for your attention.</p>
        </div>
        <p className="absolute bottom-8 left-0 right-0 text-center font-mono text-[9px] uppercase tracking-[.24em] text-[#9291B5]">Inbox · Calendar · Tasks · GitHub · AI</p>
      </section>
    </div>
  </main>;
}

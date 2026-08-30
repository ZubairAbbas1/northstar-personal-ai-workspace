"use client";

import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, Check, ChevronRight, Gamepad2, Github, KeyRound, Loader2, Mail, MessageSquare, Settings2, ShieldCheck, Unplug, X } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";

type Integration = {
  id: "gmail" | "google_calendar" | "github" | "slack" | "discord";
  name: string;
  category: string;
  description: string;
  icon: string;
  supported_scopes: string[];
  status: string;
  account_email_or_id?: string;
  token_guide?: string;
  oauth_ready: boolean;
  setup_message?: string;
  connection_error?: string;
};

type Method = "oauth" | "token" | "app_password";

type DiscordChannel = {
  id: string;
  name: string;
  guild_id: string;
  guild_name: string;
  selected: boolean;
};

const icons = { gmail: Mail, google_calendar: CalendarDays, github: Github, slack: MessageSquare, discord: Gamepad2 };
const accents = {
  gmail: "bg-[#FFEAE8] text-[#C4392E]",
  google_calendar: "bg-[#E3FBF7] text-[#00846F]",
  github: "bg-[#EEEDFE] text-[#4C3FBF]",
  slack: "bg-[#EEEDFE] text-[#4C3FBF]",
  discord: "bg-[#EEF0FF] text-[#5865F2]",
};

export default function IntegrationsPage() {
  const [items, setItems] = useState<Integration[]>([]);
  const [selected, setSelected] = useState<Integration | null>(null);
  const [method, setMethod] = useState<Method>("oauth");
  const [email, setEmail] = useState("");
  const [credential, setCredential] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [modalError, setModalError] = useState("");
  const [discordConfig, setDiscordConfig] = useState<Integration | null>(null);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [discordLoading, setDiscordLoading] = useState(false);
  const [discordSaving, setDiscordSaving] = useState(false);
  const [discordError, setDiscordError] = useState("");

  const load = async () => {
    setLoading(true);
    try { setItems(await api.getIntegrations()); }
    catch (error: any) { setNotice({ tone: "error", text: error.message || "Could not load integrations." }); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("connected")) setNotice({ tone: "success", text: "Integration connected successfully." });
    if (query.get("error")) setNotice({ tone: "error", text: "Google did not complete the connection. Check the OAuth client, callback URL, and requested permissions, then try again." });
    load();
  }, []);

  const open = (item: Integration) => {
    setSelected(item);
    setMethod(
      item.id === "slack" || item.id === "discord" ? "token" :
      item.id === "gmail" && !item.oauth_ready ? "app_password" :
      item.id === "github" && !item.oauth_ready ? "token" : "oauth"
    );
    setEmail("");
    setCredential("");
    setModalError("");
  };

  const connect = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    setModalError("");
    try {
      if (method === "oauth") {
        if (!selected.oauth_ready) {
          setModalError(selected.setup_message || "OAuth setup is required before this connection can continue.");
          return;
        }
        const result = await api.getOAuthUrl(selected.id);
        window.location.assign(result.url);
        return;
      }
      await api.connectIntegration(selected.id, {
        connection_type: method,
        token_or_key: credential,
        account_email_or_id: email || undefined,
      });
      setSelected(null);
      setNotice({ tone: "success", text: `${selected.name} connected successfully.` });
      await load();
      if (selected.id === "discord") await configureDiscord(selected);
    } catch (error: any) {
      setModalError(error.message || "Connection failed.");
    } finally { setSaving(false); }
  };

  const configureDiscord = async (item: Integration) => {
    setDiscordConfig(item);
    setDiscordChannels([]);
    setDiscordError("");
    setDiscordLoading(true);
    try { setDiscordChannels(await api.getDiscordChannels()); }
    catch (error: any) { setDiscordError(error.message || "Could not load Discord channels."); }
    finally { setDiscordLoading(false); }
  };

  const toggleDiscordChannel = (channelId: string) => {
    setDiscordChannels(current => {
      const selectedCount = current.filter(channel => channel.selected).length;
      return current.map(channel => channel.id === channelId
        ? { ...channel, selected: channel.selected ? false : selectedCount < 10 }
        : channel
      );
    });
  };

  const saveDiscordChannels = async () => {
    setDiscordSaving(true);
    setDiscordError("");
    try {
      const selectedIds = discordChannels.filter(channel => channel.selected).map(channel => channel.id);
      setDiscordChannels(await api.updateDiscordChannels(selectedIds));
      setNotice({ tone: "success", text: `Discord connected with ${selectedIds.length} selected channel${selectedIds.length === 1 ? "" : "s"}.` });
      setDiscordConfig(null);
      await load();
    } catch (error: any) { setDiscordError(error.message || "Could not save Discord channels."); }
    finally { setDiscordSaving(false); }
  };

  const disconnect = async (item: Integration) => {
    try {
      await api.disconnectIntegration(item.id);
      setNotice({ tone: "success", text: `${item.name} disconnected.` });
      await load();
    } catch (error: any) {
      setNotice({ tone: "error", text: error.message || `Could not disconnect ${item.name}.` });
    }
  };

  return <AppShell title="Integrations" description="Bring useful context in, without bringing the noise.">
    <div className="mx-auto max-w-4xl space-y-5">
      {notice && <div className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-xs font-medium ${notice.tone === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        {notice.tone === "success" ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}{notice.text}
      </div>}

      <section className="surface-flat overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[#F0F0F7] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="eyebrow text-[#4C3FBF]">Connected context</p><h2 className="mt-1 text-[17px] font-semibold text-[#1B1B2F]">Your tools</h2><p className="mt-1 text-[11px] leading-5 text-[#6B6B80]">Only successful, encrypted connections appear as active.</p></div>
          <div className="flex items-center gap-2 text-[10px] font-medium text-[#6B6B80]"><ShieldCheck className="h-4 w-4 text-[#00846F]" />Credentials encrypted at rest</div>
        </div>

        <div className="divide-y divide-[#F0F0F7]">
          {loading && <div className="flex items-center justify-center gap-2 p-12 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading integrations</div>}
          {!loading && items.map(item => {
            const Icon = icons[item.id] || KeyRound;
            const connected = item.status === "connected";
            const needsAttention = item.status === "error" || item.status === "needs_reauth";
            return <div key={item.id} className="flex flex-col gap-4 p-5 transition hover:bg-[#FAFAFE] sm:flex-row sm:items-center">
              <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${accents[item.id]}`}><Icon className="h-5 w-5" /></div>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="text-[13px] font-semibold text-[#1B1B2F]">{item.name}</h3><span className="text-[9px] font-medium uppercase tracking-wide text-[#9291A5]">{item.category}</span>{needsAttention && <span className="rounded-full bg-[#FFF4E0] px-2 py-1 text-[8px] font-semibold uppercase tracking-wide text-[#9A6500]">Needs attention</span>}</div><p className="mt-1 text-[11px] leading-5 text-[#6B6B80]">{item.description}</p>{connected && <p className="mt-1.5 truncate text-[10px] font-medium text-[#00846F]">Connected as {item.account_email_or_id}</p>}{needsAttention && <p className="mt-1.5 text-[10px] leading-5 text-[#9A6500]">{item.connection_error || "Reconnect this account to resume syncing."}</p>}{!item.oauth_ready && item.id === "google_calendar" && <p className="mt-1.5 text-[10px] text-[#6B6B80]">OAuth setup required before connecting.</p>}</div>
              {connected ? item.id === "discord" ? <div className="flex items-center gap-2 self-start sm:self-auto"><button onClick={() => configureDiscord(item)} className="rounded-full border border-[#DDE0FF] bg-[#F6F7FF] px-3 py-1.5 text-[9px] font-semibold text-[#5865F2] transition hover:bg-[#EEF0FF]"><span className="inline-flex items-center gap-1.5"><Settings2 className="h-3 w-3" />Configure</span></button><button onClick={() => disconnect(item)} aria-label="Disconnect Discord" className="rounded-full border border-[#E4E3F5] bg-white p-2 text-[#9291A5] transition hover:border-[#FFD5D1] hover:bg-[#FFEAE8] hover:text-[#C4392E]"><Unplug className="h-3 w-3" /></button></div> : <button onClick={() => disconnect(item)} className="self-start rounded-full bg-[#E3FBF7] px-3 py-1.5 text-[9px] font-semibold text-[#00846F] transition hover:bg-[#FFEAE8] hover:text-[#C4392E] sm:self-auto"><span className="inline-flex items-center gap-1.5"><Unplug className="h-3 w-3" />Connected</span></button> : <button onClick={() => open(item)} className="self-start rounded-full border border-[#E4E3F5] bg-white px-3 py-1.5 text-[9px] font-semibold text-[#4C3FBF] transition hover:bg-[#EEEDFE] sm:self-auto"><span className="inline-flex items-center gap-1">{needsAttention ? "Reconnect" : "Connect"}<ChevronRight className="h-3 w-3" /></span></button>}
            </div>;
          })}
        </div>
      </section>
    </div>

    {selected && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-sm" onMouseDown={event => { if (event.currentTarget === event.target) setSelected(null); }}>
      <form onSubmit={connect} className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start gap-3"><div className={`grid h-10 w-10 place-items-center rounded-xl ${accents[selected.id]}`}>{(() => { const Icon = icons[selected.id]; return <Icon className="h-5 w-5" />; })()}</div><div className="flex-1"><h2 className="text-base font-bold text-slate-950">Connect {selected.name}</h2><p className="mt-1 text-xs text-slate-500">Choose one secure connection method.</p></div><button type="button" onClick={() => setSelected(null)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button></div>

        <div className="mt-6 flex gap-2 rounded-xl bg-slate-100 p-1">
          {selected.id !== "slack" && selected.id !== "discord" && <button type="button" onClick={() => { setMethod("oauth"); setModalError(""); }} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${method === "oauth" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>OAuth</button>}
          {selected.id === "gmail" && <button type="button" onClick={() => { setMethod("app_password"); setModalError(""); }} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${method === "app_password" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>App password</button>}
          {(selected.id === "github" || selected.id === "slack" || selected.id === "discord") && <button type="button" onClick={() => { setMethod("token"); setModalError(""); }} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${method === "token" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>{selected.id === "discord" ? "Bot token" : "Access token"}</button>}
        </div>

        {method === "oauth" ? selected.oauth_ready ? <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/60 p-4"><p className="text-xs font-semibold text-blue-900">Continue with {selected.name}</p><p className="mt-1 text-[11px] leading-5 text-blue-800/80">You’ll review the exact permissions on the provider’s official authorization page.</p></div> : <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-semibold text-amber-900">OAuth setup required</p><p className="mt-1 text-[11px] leading-5 text-amber-800">{selected.setup_message}</p>{selected.id === "google_calendar" && <div className="mt-3 rounded-xl bg-white/70 p-3 text-[10px] leading-5 text-amber-900"><p>Add <code>GOOGLE_CLIENT_ID</code> and <code>GOOGLE_CLIENT_SECRET</code> to the backend <code>.env</code>.</p><p>Callback: <code>http://localhost:8000/api/v1/integrations/google/callback</code></p></div>}</div> : <div className="mt-5 space-y-4">
          {method === "app_password" && <div><label className="mb-1.5 block text-xs font-semibold text-slate-700">Google email</label><input required type="email" value={email} onChange={event => setEmail(event.target.value)} className="field" placeholder="you@gmail.com" /></div>}
          <div><label className="mb-1.5 block text-xs font-semibold text-slate-700">{method === "app_password" ? "16-character app password" : selected.id === "discord" ? "Discord bot token" : "Access token"}</label><input required type="password" value={credential} onChange={event => setCredential(event.target.value)} className="field" placeholder={selected.id === "discord" ? "Paste bot token" : "Paste credential"} /><p className="mt-2 text-[11px] leading-4 text-slate-500">{selected.token_guide}</p>{method === "app_password" && <p className="mt-2 text-[11px] leading-5 text-amber-700">Use a Google App Password—not your normal Gmail password. Spaces are optional.</p>}{selected.id === "discord" && <p className="mt-2 text-[11px] leading-5 text-amber-700">The bot must already be invited to your server with View Channels and Read Message History permissions.</p>}</div>
        </div>}

        {modalError && <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-[11px] leading-5 text-red-700"><X className="mt-0.5 h-3.5 w-3.5 shrink-0" />{modalError}</div>}

        <div className="mt-6 flex justify-end gap-2"><button type="button" onClick={() => setSelected(null)} className="btn-secondary">Cancel</button><button disabled={saving || (method === "oauth" ? !selected.oauth_ready : !credential.trim())} className="btn-primary">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : method === "oauth" && !selected.oauth_ready ? "Setup required" : "Continue"}</button></div>
      </form>
    </div>}

    {discordConfig && <div className="fixed inset-0 z-[75] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-sm" onMouseDown={event => { if (event.currentTarget === event.target) setDiscordConfig(null); }}>
      <section className="flex max-h-[82vh] w-full max-w-lg flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start gap-3 border-b border-slate-100 p-6"><div className="grid h-10 w-10 place-items-center rounded-xl bg-[#EEF0FF] text-[#5865F2]"><Gamepad2 className="h-5 w-5" /></div><div className="flex-1"><h2 className="text-base font-bold text-slate-950">Choose Discord channels</h2><p className="mt-1 text-xs leading-5 text-slate-500">Northstar can read only the channels selected here. Choose up to 10.</p></div><button type="button" onClick={() => setDiscordConfig(null)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button></div>
        <div className="min-h-40 flex-1 overflow-y-auto p-4">
          {discordLoading ? <div className="flex items-center justify-center gap-2 py-12 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading accessible channels</div> : discordChannels.length === 0 && !discordError ? <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">No readable text channels were found. Invite the bot to a server and grant View Channels and Read Message History.</div> : <div className="space-y-2">{discordChannels.map(channel => <label key={channel.id} className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 transition ${channel.selected ? "border-[#C9CEFF] bg-[#F6F7FF]" : "border-slate-100 hover:bg-slate-50"}`}><input type="checkbox" checked={channel.selected} onChange={() => toggleDiscordChannel(channel.id)} className="h-4 w-4 rounded border-slate-300 text-[#5865F2] focus:ring-[#5865F2]" /><div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-800">#{channel.name}</p><p className="mt-0.5 truncate text-[10px] text-slate-400">{channel.guild_name}</p></div></label>)}</div>}
          {discordError && <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-[11px] leading-5 text-red-700"><X className="mt-0.5 h-3.5 w-3.5 shrink-0" /><div className="flex-1"><p>{discordError}</p><button type="button" onClick={() => configureDiscord(discordConfig)} className="mt-2 font-semibold underline underline-offset-2">Retry channel loading</button></div></div>}
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 p-5"><p className="text-[10px] font-medium text-slate-400">{discordChannels.filter(channel => channel.selected).length}/10 selected</p><div className="flex gap-2"><button type="button" onClick={() => setDiscordConfig(null)} className="btn-secondary">Cancel</button><button type="button" onClick={saveDiscordChannels} disabled={discordSaving || discordLoading} className="btn-primary">{discordSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save channels"}</button></div></div>
      </section>
    </div>}
  </AppShell>;
}

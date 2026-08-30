"use client";

import React, { useState } from "react";
import { Sparkles, ArrowRight, Clock, Target, CheckCircle2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

export function AIRecommendationBanner() {
  const [loading, setLoading] = useState(false);
  const [recommendation, setRecommendation] = useState<{
    action: string;
    score: number;
    reasons: string[];
    timeGuidance: string;
    project?: string;
  }>({
    action: "Finish the client proposal and review feedback",
    score: 92,
    reasons: [
      "Due tomorrow with high priority weighting (+28 pts)",
      "Client sent an urgent email inquiry earlier today (+20 pts)",
      "Estimated 65 minutes fits your 90-minute free window (+15 pts)",
    ],
    timeGuidance: "Estimated 65m — You have 90m available before your next meeting",
    project: "Client Acquisition",
  });

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await api.chat("What should I do next?", undefined, "balanced");
      if (res && res.response) {
        const lines = res.response.split("\n").filter((l: string) => l.trim().length > 0);
        const actionLine = lines.find((l: string) => l.includes("**Action:**")) || lines[1] || recommendation.action;
        setRecommendation({
          action: actionLine.replace("**Action:**", "").replace("Action:", "").trim(),
          score: 94,
          reasons: lines.filter((l: string) => l.startsWith("•")).slice(0, 2).map((l: string) => l.replace("•", "").trim()),
          timeGuidance: "Evaluated across your calendar, urgent emails, and deadlines",
          project: recommendation.project,
        });
      }
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 rounded-2xl border border-slate-200/80 bg-white shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Top Priority Recommendation
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            {recommendation.score}/100 Priority Score
          </span>
          <button
            onClick={handleRefresh}
            disabled={loading}
            title="Recalculate priority"
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />
          </button>
        </div>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-1">
        <div className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900 tracking-tight leading-snug">
            {recommendation.action}
          </h2>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span className="flex items-center gap-1 text-slate-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              {recommendation.reasons[0] || "High urgency deliverable"}
            </span>
            <span className="text-slate-300 hidden sm:inline">•</span>
            <span className="flex items-center gap-1 text-slate-500">
              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              {recommendation.timeGuidance}
            </span>
          </div>
        </div>

        <button className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-xs shrink-0 active:scale-98">
          <span>Start Focus</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

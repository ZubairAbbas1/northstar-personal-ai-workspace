"use client";

import React from "react";
import Link from "next/link";
import { Users, Clock, ArrowUpRight, Sparkles, MapPin } from "lucide-react";
import { formatTimeOnly } from "@/lib/utils";

interface MeetingProps {
  meeting?: {
    id: string;
    summary: string;
    start: string;
    end: string;
    attendees: string[];
    location?: string;
  };
}

export function MeetingPrepCard({ meeting }: MeetingProps) {
  const defaultMeeting = {
    id: "sample-1",
    summary: "Sprint Planning & Architecture Sync",
    start: new Date(Date.now() + 1000 * 60 * 45).toISOString(),
    end: new Date(Date.now() + 1000 * 60 * 105).toISOString(),
    attendees: ["sarah.c@company.com", "alex.m@company.com", "michael.t@company.com"],
    location: "Google Meet",
  };

  const item = meeting || defaultMeeting;

  return (
    <div className="p-5 rounded-2xl border border-slate-200/80 bg-white shadow-card space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
            Next Scheduled Meeting
          </span>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-50 text-blue-700">
          In 45 mins
        </span>
      </div>

      <div>
        <h3 className="text-base font-bold text-slate-900 leading-snug">{item.summary}</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
          <div className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>
              {formatTimeOnly(item.start)} – {formatTimeOnly(item.end)}
            </span>
          </div>
          {item.location && (
            <div className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              <span>{item.location}</span>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-slate-100 pt-3">
        <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
          <span className="font-semibold flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-slate-400" />
            <span>{item.attendees.length} Attendees</span>
          </span>
          <span className="text-[11px] text-slate-400 truncate max-w-[160px]">
            {item.attendees.join(", ")}
          </span>
        </div>

        {/* AI Brief synthesis shortcut */}
        <Link
          href="/calendar"
          className="flex items-center justify-between p-2.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-900 text-xs font-semibold transition-colors"
        >
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-purple-600" />
            <span>View AI Meeting Brief & Attendee Threads</span>
          </div>
          <ArrowUpRight className="w-3.5 h-3.5 text-purple-600" />
        </Link>
      </div>
    </div>
  );
}

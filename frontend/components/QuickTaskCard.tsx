"use client";

import React, { useState } from "react";
import { Check, Clock, Calendar as CalendarIcon, Tag } from "lucide-react";
import { cn, formatDate, getPriorityBadgeColor } from "@/lib/utils";
import { api } from "@/lib/api";

interface TaskProps {
  task: {
    id: string;
    title: string;
    description?: string | null;
    priority: string;
    status: string;
    due_date?: string | null;
    estimated_minutes: number;
    project?: { name: string } | null;
  };
  onUpdate?: () => void;
}

export function QuickTaskCard({ task, onUpdate }: TaskProps) {
  const [completed, setCompleted] = useState(task.status === "completed");
  const [isUpdating, setIsUpdating] = useState(false);

  const toggleComplete = async () => {
    const nextStatus = completed ? "todo" : "completed";
    setCompleted(!completed);
    setIsUpdating(true);
    try {
      await api.updateTask(task.id, { status: nextStatus });
      if (onUpdate) onUpdate();
    } catch {
      setCompleted(completed);
    } finally {
      setIsUpdating(false);
    }
  };

  const badge = getPriorityBadgeColor(task.priority);

  return (
    <div
      className={cn(
        "p-4 rounded-xl border transition-all duration-150 flex items-start justify-between gap-4 bg-white",
        completed ? "border-slate-100 bg-slate-50/40 opacity-70" : "border-slate-200/80 hover:border-slate-300 hover:shadow-subtle"
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <button
          onClick={toggleComplete}
          disabled={isUpdating}
          className={cn(
            "w-5 h-5 rounded-md border flex items-center justify-center transition-colors mt-0.5 shrink-0",
            completed
              ? "bg-emerald-600 border-emerald-600 text-white"
              : "border-slate-300 hover:border-indigo-600 text-transparent"
          )}
        >
          <Check className="w-3.5 h-3.5 stroke-[3]" />
        </button>

        <div className="min-w-0">
          <p
            className={cn(
              "text-sm font-semibold text-slate-900 truncate leading-snug",
              completed && "line-through text-slate-400"
            )}
          >
            {task.title}
          </p>

          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span
              className={cn(
                "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border",
                badge.bg,
                badge.text,
                badge.border
              )}
            >
              {task.priority}
            </span>

            {task.due_date && (
              <span className="text-xs text-slate-500 flex items-center gap-1">
                <CalendarIcon className="w-3 h-3 text-slate-400" />
                <span>{formatDate(task.due_date)}</span>
              </span>
            )}

            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>{task.estimated_minutes}m</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import * as React from "react";

import { StatusBadge } from "@/components/hr/status-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Offer } from "@/lib/hr/types";

/**
 * Onboarding table (acceptance criterion 7) — offers in
 * accepted | joined | not_joined with inline Mark Joined / Mark Not
 * Joined actions on the ones still awaiting a join.
 */
interface Props {
  offers: Offer[];
  onMarkJoined: (offer: Offer) => void;
  onMarkNotJoined: (offer: Offer) => void;
  onOpen: (offer: Offer) => void;
}

export function OnboardingTable({
  offers,
  onMarkJoined,
  onMarkNotJoined,
  onOpen,
}: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Candidate</TableHead>
            <TableHead className="hidden md:table-cell">Job</TableHead>
            <TableHead className="w-32">Joining date</TableHead>
            <TableHead className="hidden sm:table-cell w-28">
              Days to join
            </TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="hidden lg:table-cell">No-show reason</TableHead>
            <TableHead className="w-[13rem] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {offers.map((o) => {
            const awaiting = o.status === "accepted";
            return (
              <TableRow
                key={o.id}
                onClick={() => onOpen(o)}
                className="cursor-pointer transition-colors hover:bg-muted/40"
              >
                <TableCell>
                  <p className="font-medium leading-tight">
                    {o.candidate_name ?? "—"}
                  </p>
                  {o.candidate_email && (
                    <p className="text-xs text-muted-foreground">
                      {o.candidate_email}
                    </p>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell text-sm">
                  {o.job_title ?? "—"}
                  {o.department && (
                    <p className="text-[11px] text-muted-foreground">
                      {o.department}
                    </p>
                  )}
                </TableCell>
                <TableCell className="text-sm">
                  {o.joining_date ?? "—"}
                </TableCell>
                <TableCell className="hidden sm:table-cell text-sm tabular-nums">
                  {awaiting ? daysToJoin(o.joining_date) : "—"}
                </TableCell>
                <TableCell>
                  <StatusBadge kind="offer" status={o.status} />
                </TableCell>
                <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                  {o.not_joined_reason ?? "—"}
                </TableCell>
                <TableCell
                  className="text-right"
                  onClick={(e) => e.stopPropagation()}
                >
                  {awaiting ? (
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onMarkJoined(o)}
                      >
                        Mark joined
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onMarkNotJoined(o)}
                      >
                        Not joined
                      </Button>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {o.joined_at
                        ? `Joined ${new Date(o.joined_at).toLocaleDateString()}`
                        : "Closed"}
                    </span>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function daysToJoin(joiningDate: string | null): string {
  if (!joiningDate) return "—";
  const target = new Date(`${joiningDate}T00:00:00`);
  if (Number.isNaN(target.getTime())) return "—";
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round(
    (target.getTime() - today.getTime()) / 86_400_000,
  );
  if (diff === 0) return "Today";
  if (diff > 0) return `in ${diff}d`;
  return `${Math.abs(diff)}d overdue`;
}

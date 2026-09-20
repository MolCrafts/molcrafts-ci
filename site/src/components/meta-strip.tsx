import type { JSX, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface MetaFact {
  label: string;
  value: ReactNode;
  /** Quantities and identifiers are mono with tabular figures. */
  mono?: boolean;
}

export interface MetaStripProps {
  facts: MetaFact[];
  className?: string;
}

/**
 * The operational posture of one object, in a single band.
 *
 * This is what replaces a grid of StatCards: three to eight facts a user needs
 * to orient, at one size, in one row. It is not an identity dump — anything
 * that does not change the next action belongs in a detail tab.
 *
 * No border and no surface of its own: a band of facts is not something the
 * reader can open, drag or delete, so it does not get a box. A rule under it
 * and hairlines between the cells carry the structure instead.
 */
export const MetaStrip = ({ facts, className }: MetaStripProps): JSX.Element => (
  <dl
    className={cn(
      "flex flex-wrap items-center gap-y-2 border-b border-border pb-3",
      className,
    )}
  >
    {facts.map((fact, i) => (
      <div
        key={fact.label}
        className={cn(
          "flex min-w-0 flex-col gap-hairline px-4",
          i === 0 && "pl-0",
          i > 0 && "border-l border-border",
        )}
      >
        <dt className="text-micro text-muted-foreground whitespace-nowrap">{fact.label}</dt>
        <dd
          className={cn(
            "truncate text-body font-medium text-foreground",
            fact.mono && "font-mono tabular-nums",
          )}
        >
          {fact.value}
        </dd>
      </div>
    ))}
  </dl>
);

export interface Measure {
  label: string;
  /** Already formatted — this component does not decide precision. */
  value: string;
  /** 0–100, drives the bar. Omit when the value is not a percentage. */
  percent?: number;
  /** Bar colour class, e.g. `bg-status-warning`. Defaults to the accent. */
  tone?: string;
}

export interface MeasureBandProps {
  measures: Measure[];
  className?: string;
}

/**
 * Several measures of one thing, read together.
 *
 * Coverage has four totals and they are one reading, not four headlines — so
 * they share a band with the bar doing the comparing, instead of becoming four
 * equal hero tiles. Boxing that band would put the tiles back.
 */
export const MeasureBand = ({ measures, className }: MeasureBandProps): JSX.Element => (
  <dl
    className={cn(
      "flex flex-wrap border-b border-border pb-3",
      className,
    )}
  >
    {measures.map((m, i) => (
      <div
        key={m.label}
        className={cn(
          "flex min-w-40 flex-1 flex-col gap-1 px-4",
          i === 0 && "pl-0",
          i > 0 && "border-l border-border",
        )}
      >
        <dt className="text-micro text-muted-foreground">{m.label}</dt>
        <dd className="font-mono text-title font-medium tabular-nums text-foreground">
          {m.value}
        </dd>
        {m.percent != null && (
          <div className="h-1 w-full overflow-hidden rounded-hairline bg-sunken">
            <div
              className={cn("h-full", m.tone ?? "bg-accent")}
              style={{ width: `${Math.max(0, Math.min(100, m.percent))}%` }}
            />
          </div>
        )}
      </div>
    ))}
  </dl>
);

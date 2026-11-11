import type { JSX } from "react";
import {
  ContentSection, MeasureBand, Table, TableBody, TableCell,
  TableHead, TableHeader, TableRow,
} from "@molcrafts/ui";
import type { ScientificBenchmark } from "@/lib/payload";

/** A producer-owned scientific matrix, with the actual campaign environment. */
export function ScientificBenchmarkView({ benchmark: b }: { benchmark: ScientificBenchmark }): JSX.Element {
  const s = b.summary, e = b.environment;
  const show = (value: unknown): string => value == null ? "unknown" : typeof value === "object" ? JSON.stringify(value) : String(value);
  const gpus = e.gpus as unknown[];
  const hardware = `H1: CPU=${show(e.cpu_model)}; physical cores=${show(e.physical_cores)}; logical CPUs=${show(e.logical_cpus)}; requested OMP/BLAS threads=${b.threads}; GPU=${gpus.length ? gpus.map(show).join("; ") : e.gpu_query_available === false ? "not observed" : "none detected"}; host RAM=${show(e.host_memory_bytes)} bytes; OS=${show(e.os)}; Python=${show(e.python)}; warm samples=${b.repeats}; warmup(s)/sample=${b.warmup}; ${b.started}.`;
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <p className="break-all text-label text-muted-foreground">Campaign: {b.campaign_id}</p>
      <MeasureBand measures={[
        { label: "Required", value: String(s.required) },
        { label: "Numerical passed", value: String(s.passed), tone: "completed" },
        { label: "Numerical failed", value: String(s.failed), tone: "failed" },
        { label: "Incomplete", value: String(s.incomplete), tone: "warning" },
        { label: "Optional unavailable", value: String(s.optional_unavailable), tone: "cancelled" },
        { label: "Performance regressions", value: String(s.performance_regressions), tone: s.performance_regressions ? "failed" : "ready" },
      ]} />
      <p className="text-label">Historical comparison: {s.historical_status}. Times are warm end-to-end seconds; ratios and eligibility come from the producer.</p>
      <ContentSection title="Scientific benchmark matrix">
        <div className="min-w-0 max-w-full overflow-x-auto">
          <Table className="min-w-[60rem]" aria-label="Scientific benchmark matrix" tabIndex={0}>
            <TableHeader><TableRow>
              <TableHead>Method / model / task</TableHead><TableHead>Systems</TableHead>
              {b.matrix.columns.map(col => <TableHead key={col}>{col}</TableHead>)}
              <TableHead>Hardware / environment</TableHead>
            </TableRow></TableHeader>
            <TableBody>{b.matrix.rows.map(row => <TableRow key={row.id}>
              <TableCell className="align-top whitespace-normal"><span title={row.id}>{row.label}</span></TableCell>
              <TableCell className="align-top whitespace-normal">{row.systems.map((system, i) => <p key={i}>{system}</p>)}</TableCell>
              {b.matrix.columns.map(col => <TableCell key={col} className="min-w-64 align-top whitespace-normal break-words">
                {row.values[col]!.map((value, i) => <p key={i}>{value}</p>)}
              </TableCell>)}
              <TableCell className="min-w-48 align-top whitespace-normal">{row.notes}</TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </div>
        <p className="mt-3 text-label text-muted-foreground">{hardware}</p>
      </ContentSection>
      <details className="min-w-0 rounded border border-border p-3">
        <summary className="cursor-pointer">Actual environment and protocol</summary>
        <pre className="mt-3 max-w-full overflow-auto whitespace-pre-wrap break-words text-label">{JSON.stringify({ environment: e, source: b.source, protocol: b.protocol, threads: b.threads, repeats: b.repeats, warmup: b.warmup, started: b.started }, null, 2)}</pre>
      </details>
      <details className="min-w-0 rounded border border-border p-3">
        <summary className="cursor-pointer">Roadmap evidence</summary>
        <pre className="mt-3 max-w-full overflow-auto whitespace-pre-wrap break-words text-label">{JSON.stringify(b.roadmap, null, 2)}</pre>
      </details>
      <details className="min-w-0 rounded border border-border p-3">
        <summary className="cursor-pointer">Execution results and observations</summary>
        <pre className="mt-3 max-w-full overflow-auto whitespace-pre-wrap break-words text-label">{JSON.stringify(b.results, null, 2)}</pre>
      </details>
    </div>
  );
}

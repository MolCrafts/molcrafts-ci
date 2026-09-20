/**
 * The streams this app knows how to open, as data.
 *
 * Kept out of the component file so the resolution rule — which on-disk kind
 * opens which tab — can be exercised without rendering anything. Getting this
 * wrong is invisible in a type check and shows up as a click that does nothing.
 */
export interface StreamKind {
  /** Tab id. `conv` is Coverage (Codecov replacement), not conformance. */
  id: string;
  label: string;
  /** On-disk kind names this tab answers to. */
  aliases: string[];
  order: number;
}

export const STREAM_KINDS: StreamKind[] = [
  { id: "tests", label: "Tests", aliases: ["tests", "test"], order: 10 },
  { id: "conv", label: "Coverage", aliases: ["coverage", "cov", "conv"], order: 20 },
  { id: "benchmark", label: "Benchmark", aliases: ["benchmark"], order: 30 },
  { id: "regression", label: "Regression", aliases: ["regression", "numerical"], order: 40 },
  { id: "molrec", label: "MolRec", aliases: ["molrec"], order: 50 },
  { id: "conformance", label: "Conformance", aliases: ["conformance"], order: 60 },
];

export function kindMatches(kinds: string[], aliases: string[]): boolean {
  const set = new Set(kinds.map((k) => k.toLowerCase()));
  return aliases.some((a) => set.has(a.toLowerCase()));
}

import type { ScientificBenchmark } from "../../src/lib/payload";

/** Synthetic display fixture; these are not scientific acceptance results. */
export function scientificBenchmark(): ScientificBenchmark {
  return {
    schema: "atomiverse.scientific-benchmark/1", campaign_id: "campaign-one",
    summary: { required: 4, passed: 4, failed: 0, incomplete: 0, optional_unavailable: 0,
      complete: true, performance_regressions: 0, historical_status: "unbaselined" },
    matrix: { columns: ["atv.cpu.direct", "pyscf.cpu"], rows: [{
      id: "scf.rhf.sto-3g.energy", label: "RHF / STO-3G / energy",
      systems: ["Water molecule", "Water chain, 16 molecules"],
      values: {
        "atv.cpu.direct": ["water-1: pass; 0.001 s; 1.5× vs pyscf.cpu", "water-16: pass; 0.9 s; 1.11× vs pyscf.cpu"],
        "pyscf.cpu": ["water-1: pass; 0.0015 s", "water-16: pass; 1 s"],
      }, notes: "H1; FP64; reference=pyscf.cpu",
    }] },
    environment: { cpu_model: "Synthetic test CPU", physical_cores: 8, logical_cpus: 16,
      host_memory_bytes: 34359738368, gpus: ["Synthetic test GPU, 24 GiB"],
      os: "Synthetic OS", python: "3.12", affinity: [0, 1, 2, 3], scheduler: { SLURM_JOB_ID: "test-only" } },
    source: { commit: "abc123", dirty: true, build_verified: true },
    protocol: { selection_partial: false, timing_scope: "warm_e2e" },
    threads: 8, repeats: 5, warmup: 1, started: "2026-10-26T12:00:00Z",
    roadmap: [{ capability_id: "hf.rhf.energy", backend: "cpu", mark: "◐", reason: "local source" }],
    results: ["water-1", "water-16"].flatMap(system_id => ["atv.cpu.direct", "pyscf.cpu"].map(participant_id => ({
      row_id: "scf.rhf.sto-3g.energy", system_id, participant_id, required: true,
      status: "completed", numerical: "pass",
    }))),
  };
}

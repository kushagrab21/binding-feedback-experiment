# Write-up figures — plotting package

Self-contained. Data lives in `data/` as five CSVs distilled from the
repository's deterministic analysis outputs (phase6_analysis/results.md,
v2_ladder/analysis/results.{md,json}, v3_window/analysis/results.md).
Scripts read ONLY those CSVs; nothing calls the network or touches the repo.

## Run

    python3 plot_all.py        # figures 1-4 (data charts)  -> ./figures/
    python3 plot_diagrams.py   # figures 5-6 (diagrams)     -> ./figures/

Requires python3 + matplotlib + numpy.

## Files

    data/exp1_results.csv      Experiment 1 per-cell results (2 models x 2 modes)
    data/exp2_ladder.csv       Experiment 2 ladder: results, McNemar b/c/p, exit
                               classification (advisory 4 exits, binding 3), rescue split
    data/exp3_cells.csv        Experiment 3 per model x tier cells with McNemar
    data/exp3_matrix.csv       Experiment 3 delta-vs-k and false-DONE-rate-vs-k (long form)
    data/mediator_scatter.csv  One row per cell across experiments 2 and 3: false-DONE rate vs delta
    style.py                   Shared palette and matplotlib rc (light mode)
    plot_all.py                Figures 1-4 from the CSVs
    plot_diagrams.py           Figure 5 (exit decision trees) and 6 (workflow pipeline)

## Figure -> section mapping

    fig1_experiment1_2x2.png       Section 4 (Experiment 1 results)
    fig2_capability_window.png     Section 5 (the signature figure)
    fig3_composition_window.png    Section 6 (beside the delta-vs-k matrix)
    fig4_mediator_scatter.png      Section 7 (the mechanism unified)
    fig5_exit_trees.png            Section 5 (exit classification block)
    fig6_workflow.png              Section 5 (workflow block; also covers 3 and 6)

## Notes for the plotting agent

- Colors and chrome live in style.py; change them there, not per-figure.
- In fig3, Gemini-2.5-Flash-Lite is drawn dashed because its values are
  byte-identical to GPT-4o-mini's; do not "fix" the overlap by deleting a series.
- In fig4, the dashed diagonal is a reference line (delta = false-DONE rate),
  not a regression fit; keep the legend wording that says so.
- fig2 marker fill encodes McNemar significance (filled = p < 0.05); keep it.

## Verification

    python3 verify_data.py

Recomputes every value in data/*.csv from the repository's deterministic
analysis outputs (phase6_analysis/results.json, v2_ladder/analysis/results.json,
v3_window/analysis/results.json) and diffs them. Exits 0 only if every value
matches. It looks for the repository at
~/Desktop/Experiment_binding_agent/binding-feedback-experiment
(override with the REPO_BASE environment variable).
Last container run: 307 values checked, 0 discrepancies.

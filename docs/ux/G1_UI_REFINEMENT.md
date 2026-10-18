# G1 — information architecture and visual refinement

Status: **PASS for the implemented P0/P1 UI and exercised layouts**. Full accessibility conformance is outside the evidence collected in this phase.

Implementation: preserve the original Next.js application, component library and all nine routes. DeepInsight Lite is the product; London Office Intelligence is the workspace; DeepInsight AI is the primary assistant. Sidebar groups are AI Workspace, Market Intelligence and Monitoring. The advanced /ask capability remains available as Saved-record research; no business capability or record was deleted.

Suggestions now fill and focus an editable question rather than immediately invoke the model. Sources & capabilities is a real disclosure with data/report/monitor links and truthful capability limits. History searches titles (labelled accordingly), shows saved activity timestamps and uses a true empty state. ISO/epoch timestamps and missing dates are handled explicitly after a real browser found Invalid Date from the native ISO response.

Mobile sidebar has keyboard wrapping, Escape close, return focus and inert background. Context and uncertainty text is readable; document/source diagnostics are progressively disclosed. Dark-mode form labels inherit workspace foreground after a measured regression (old foreground rgb(15,23,42), background rgb(43,46,51)). No input-method/avatar software was touched.

Validation: P0 production build and 14 tests passed. P1 integrated build compiled and passed its engineering checks, then runtime acceptance found timestamp, context navigation and inherited dark-text defects; those were repaired before final publication. Final build, responsive/theme checks and screenshots are recorded in G4_FINAL_ACCEPTANCE.md. Full WCAG conformance and physical mobile-keyboard behavior are not claimed.

# Frozen input erratum — 2026-10-18

Status: **INVALID INPUT** for factual-quality scoring.

The `news_planning` case in `cases.json` is the **as-sent input**. It must not be edited after the paid call. Its `CITY_SILK` excerpt says "Planning and Transportation Committee". The preserved [City of London article](../../../app/data/product/source-qualification/city-silk-street.html) actually says **"Planning Applications Sub-Committee"**. The model repeated the inaccurate benchmark excerpt. Its output on that case is not a valid measure of factual fidelity, and the automatic 100/100 row is excluded from quality conclusions.

Before any separately authorised future round, make a new versioned dataset with the exact committee name and validate every named entity in each excerpt against the saved original. Do not replace this as-run file or reinterpret the historical answer as correct.

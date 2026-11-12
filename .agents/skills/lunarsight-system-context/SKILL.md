---
name: lunarsight-system-context
description: Explain or change HOSA using the current system behavior, scientific evidence, and documented coverage. Use when a task needs project context or a technically accurate explanation of its purpose and limits.
---

# HOSA System Context

HOSA evaluates whether a lunar observation point, time window, and mission requirements meet geometric illumination and Earth-centre line-of-sight conditions. NASA LOLA/PGDA terrain, JPL Horizons ephemerides, terrain horizons, uncertainty, provenance, and validation gates support the deterministic backend. It is an educational planning prototype, not landing certification, a power/thermal model, or a radio link budget.

## Read the live system

- Start with `README.md`, then inspect the matching code in `backend/app/mission`, `backend/app/planning`, `backend/app/point_analysis`, and `backend/app/assistant`.
- Treat active schemas, engine behavior, versioned data, and validation code as the evidence for what runs today. Mark proposal docs, notebooks, and old scenario notes as historical when they disagree.
- Follow the data from receipts and catalog metadata through the engine result and provenance. Do not infer scientific coverage from the presence of an archive alone.
- Keep point-specific JPL coverage separate from general model knowledge. Existing P1 snapshots do not establish Horizons coverage for another observer.
- Preserve known data limits: Site06 ROI is unavailable at source; Site20 and Site20v2 share a location group; missing quality/frame/unit evidence stays missing.

## Explain conclusions

Separate measured or calculated facts, model interpretation, and uncertainty. The backend owns metrics, candidate ranking, validation, and PASS/FAIL/INDETERMINATE. Cite verifiable project or catalog sources. If the engine lacks coverage, state what it cannot establish and identify the required data or input; do not fill gaps from memory.

## Inputs and outputs

Inputs are a question, repository and catalog state, and any specific engine result. Outputs are a concise project explanation or a code change tied to current contracts, with source paths and limits. Before changing a domain rule or expected scientific status, locate its request, data/source hashes, validation evidence, and regression coverage. Stop and report the blocked evidence when the repository or source data cannot support the requested claim.

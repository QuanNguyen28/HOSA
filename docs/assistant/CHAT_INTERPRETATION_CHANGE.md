# Grounded mission explanations

The assistant uses the existing mission/planning engines and data. `backend/app/assistant/interpretation.py` defines what the computed metrics mean, which mission questions they answer and what cannot be inferred from them. These definitions are interpretation guidance, not canned responses or invented site results.

After a computation, the assistant copies compact facts tied to the exact result and candidate: final/nominal decisions, hard/soft checks, metric bounds, validation reasons, contact evidence and selected recorded events. Requested minimum hours use the actual mission duration. The model returns prose and evidence references; unknown references or mismatched states trigger repair, then an explicit partial failure if necessary. Scientific results survive an explanation failure.

The model receives a qualitative view by default: decisions, relevant check states, validation causes and metric meanings. Numerical values remain in the complete engine result and saved evidence, and are exposed for explicit questions about quantities, bounds, tables or window times. A request to explain rather than list numbers keeps the qualitative view. This is display/context selection, not a change to scientific computation. Response length is unrestricted.

Session state retains the last engine evidence for explanation-only follow-ups. Changed mission inputs require new computation. An explanation cannot overwrite the working query with an unevaluated suggestion. Required mission fields are validated against the existing schemas before execution; a conceptual question does not require a mission date, and optional soft preferences do not block calculation.

The terminal prints prose first. `/result` reveals raw numerical details when requested, `/new` creates a new persistent session, and `/unicode` checks UTF-8 locally. The PowerShell launcher configures the console session only, can start a hidden loopback API, and respects configured model/failover unless explicit overrides are requested.

Evidence/state validation does not constitute full semantic verification of prose. The model must still avoid unsupported physical causes, battery/energy estimates, RF link conclusions or landing certification. The current data and validation coverage remain the limits of every conclusion. See [release scope and checks](BE_LLM_RELEASE.md).

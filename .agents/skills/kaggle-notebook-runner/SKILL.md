---
name: kaggle-notebook-runner
description: Import, execute and verify private Kaggle notebooks for reproducible CPU pipelines. Use for Save & Run All, logs, and output export.
---

# kaggle-notebook-runner

Inputs: reviewed notebook, authorized Kaggle session, CPU and expected outputs. Outputs: private notebook URL, version ID/status, execution logs and verified artifacts.

1. Open the authorized Kaggle editor. Verify Private and CPU. If credentials or account verification are required, hand off to the user through the safe interface.
2. Import the self-contained ipynb. Enable Internet only when the task needs acquisition from authorized sources; check actual endpoint reachability and package availability. Keep nonessential raw data outside /kaggle/working.
3. Choose Save & Run All (Commit). Inspect the actual version status and output log; fix failures and save a new version. A draft, scheduled job or success toast is not a successful run.
4. Download the artifact and check its byte count, archive integrity and execution report. When necessary, fall back to the [official Kaggle CLI](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md) with an existing authorized account credential. Never solicit tokens in chat or make a notebook public.

References: [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks). Completion evidence: version status and verified ZIP from the completed commit.

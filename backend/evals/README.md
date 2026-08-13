# Pangdun Agent real-source evaluation

This evaluation calls the configured DeepSeek model with public pages and never writes to the CRM database.

The fixture contains ten official About, Contact, or imprint pages from technology publications. Expected fields only cover facts visible on the selected page. A missing model result counts as a failed check; failed samples are not removed from the accuracy denominator.

Run the public-page fetch check without calling the model:

```powershell
backend\.venv\Scripts\python.exe backend\evals\run_agent_real_eval.py --fetch-only
```

Run the complete evaluation:

```powershell
backend\.venv\Scripts\python.exe backend\evals\run_agent_real_eval.py
```

Run the social-profile URL evaluation:

```powershell
backend\.venv\Scripts\python.exe backend\evals\run_agent_real_eval.py --samples backend\evals\agent_social_samples.json
```

Run one sample while tuning prompts:

```powershell
backend\.venv\Scripts\python.exe backend\evals\run_agent_real_eval.py --id techspot-about
```

Full JSON responses are written to the ignored `backend/evals/results/` directory. Do not turn an evaluation result into CRM data without using the normal human review flow.

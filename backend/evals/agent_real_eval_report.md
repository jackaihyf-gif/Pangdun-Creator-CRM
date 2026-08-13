# DeepSeek V4 Flash real-source evaluation

Date: 2026-08-13
Model: `deepseek-v4-flash`
Mode: public URL fetch -> JSON proposal -> evidence/confidence guard; no CRM writes

## Result

- Public source fetch: 10 / 10
- Completed model responses: 10 / 10
- Strict expected-field accuracy: 28 / 29 (96.6%)
- Perfect samples: 9 / 10
- Final-run tokens: 25,935
- Proposed fields without exact field-level evidence: 22; none received a score above the 0.49 guardrail or qualified for automatic preselection

| Sample | Checks | Result |
| --- | ---: | --- |
| Hardware Times | 3 / 3 | name, website channel, 1M monthly audience |
| TweakTown | 3 / 3 | name, website channel, Australia |
| TechSpot | 3 / 3 | name, website channel, 8M monthly audience |
| PC Guide | 3 / 3 | name, website channel, United Kingdom |
| Android Authority | 2 / 3 | name and channel matched; general inbox omitted after three specialized business inboxes |
| igor'sLAB | 3 / 3 | name, website channel, public phone |
| Liliputing | 2 / 2 | name and website channel |
| Hardwareluxx | 2 / 2 | name and website channel |
| Cowcotland | 2 / 2 | name and website channel |
| Canaltech | 5 / 5 | name, channel, Brazil, 24M monthly audience, editorial inbox |

## What the first run exposed

TechSpot's long staff page caused the first response to hit the model output limit. The extraction prompt was changed to return no more than three contacts, prioritizing editorial, PR, sales, and sample-shipping contacts with explicit contact details. A targeted rerun and the final unified ten-sample run then completed successfully.

## Remaining risks

1. The model does not reliably obey the requirement that every proposed field include exact source evidence. The server-side normalization guard remains necessary.
2. Canaltech's proposal inferred a YouTube URL from a channel name. Because it lacked exact evidence, it remained low-confidence and was not preselected.
3. Obfuscated addresses such as `[email protected]` can be extracted as placeholders. The model warned about this, but a human still needs to reject it.
4. The three-contact cap can omit a general inbox when several specialized inboxes are present. This is preferable to truncating the entire response, but the review UI should continue to expose the source.

## Decision

The model is suitable for human-reviewed extraction in the current two-to-three-person workflow. It is not suitable for unattended writes. Keep field evidence, the confidence cap, duplicate checks, and manual confirmation as mandatory controls.

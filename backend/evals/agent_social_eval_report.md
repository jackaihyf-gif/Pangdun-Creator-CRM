# Social profile URL evaluation

Date: 2026-08-13
Model: `deepseek-v4-flash`
Samples: four YouTube channels, three TikTok profiles, three Instagram profiles
Mode: current production URL fetch -> JSON proposal; no CRM writes

## Samples

| Platform | Profile |
| --- | --- |
| YouTube | Linus Tech Tips |
| YouTube | Gamers Nexus |
| YouTube | Hardware Unboxed |
| YouTube | der8auer |
| TikTok | @nedalextech |
| TikTok | @pinkxxiny |
| TikTok | @mosclave |
| Instagram | @dudatech.oficial |
| Instagram | @masters.of.tech |
| Instagram | @nico_cpk |

## Current production result

- Strict checks: 12 / 20 (60%)
- YouTube: one of four profiles completed; three were rejected before model invocation because the HTML exceeded the 2 MB safety limit.
- TikTok: all three requests returned HTTP 200 but only the generic 22-character text `TikTok - Make Your Day`; platform detection was stable, handle recovery from the URL was not.
- Instagram: all three public pages exposed the display name and handle in the HTML title, so name and platform checks passed.
- No test record was written to the CRM database.

The fixture description is not shown to the model. The final public URL is used as the source label to prevent expected account names from leaking through test metadata.

## Official/public metadata feasibility probe

A separate no-model probe found stable identity metadata for all ten profiles:

- YouTube: the first ~1 MB of the public channel HTML contained Open Graph title, description, and canonical channel URL for 4 / 4 profiles. The full pages ranged from roughly 1.5 MB to 2.5 MB.
- TikTok: the public oEmbed endpoint returned display name and canonical author URL for 3 / 3 creator profiles.
- Instagram: the public HTML title returned display name and handle for 3 / 3 profiles.

This means a small platform-aware identity adapter can likely raise basic identity ingestion from 60% to 100% without relaxing the general 2 MB page limit. It would still not provide reliable follower counts across all three platforms.

## TikTok-Api feasibility check (2026-08-13)

Tested `TikTokApi 7.3.3` with `Playwright 1.62.0` and its bundled Chromium 151 on the local CRM host. The test deliberately used no personal browser cookies, no supplied `ms_token`, no login account, and no proxy.

- Session creation succeeded and generated an `msToken` automatically.
- Starting from both the TikTok homepage and the target creator profile produced valid browser sessions and cookies.
- `user.info()` returned `EmptyResponseException` for `nedalextech`, `pinkxxiny`, and `mosclave`; the library reported that TikTok detected bot traffic.
- Result: 0 / 3 public profiles returned user details or follower statistics.
- TikTok's public creator oEmbed endpoint still returned HTTP 200 and the correct display name and canonical profile URL for all 3 / 3 profiles, but not follower statistics in the oEmbed JSON.

Conclusion: the unofficial API is not suitable as Pangdun's anonymous production provider on the current network. Making it work would require at least a visible/authenticated browser session or proxy experimentation, adding operational and account-risk costs that are disproportionate to the three TikTok records currently stored.

## Lightweight identity adapter verification (2026-08-13)

The production-oriented lightweight adapter was verified against the same six public profiles without login cookies, proxies, or follower scraping:

- TikTok official creator oEmbed: 3 / 3 display names and canonical profile URLs.
- Instagram public profile titles: 3 / 3 display names and canonical profile URLs.
- Overall identity result: 6 / 6.

The adapter intentionally does not propose follower counts for either platform. Each profile link records its public source, verification date, and confidence before entering the existing human review flow.

## Product decision

1. Keep the generic webpage extractor for media sites and contact pages.
2. Detect YouTube, TikTok, and Instagram profile URLs before generic HTML extraction.
3. Use a small identity adapter per platform to obtain canonical URL, handle, display name, description, and available public metadata.
4. Use official APIs for repeatable follower-count refreshes. YouTube's channel resource exposes `statistics.subscriberCount`; TikTok profile statistics require the relevant API permission.
5. Continue sending normalized source text to DeepSeek for category, country, contact, and risk suggestions, but do not ask the model to reconstruct platform facts that a deterministic adapter can provide.

## Methodology correction

The earlier website evaluation used descriptive source labels containing publication names. That did not affect email, country, or audience checks, but it made publication-name checks too easy. The evaluator now always exposes only the final URL to the model. Future comparison runs should use this corrected method.

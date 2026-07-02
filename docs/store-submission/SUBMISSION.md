# NVDA Add-on Store submission packet

This document has everything needed to submit **Sarvam AI assistant** to the
official NVDA Add-on Store, based on NV Access's
[submission guide](https://github.com/nvaccess/addon-datastore/blob/master/docs/submitters/submissionGuide.md).

## How the store works (summary)

- Submission is **not** a manual pull request. You fill in a **GitHub issue
  form** on NV Access's `addon-datastore` repo. A bot reads your add-on's
  manifest from the download URL, generates the metadata JSON, and opens the PR
  for you.
- **VirusTotal** scans the `.nvda-addon`; automated validation checks run on the
  PR. If they pass and you are an approved submitter, the PR auto-merges and the
  add-on appears in the store.
- **First-time approval:** because this is a new add-on ID (`sarvamAI`), an NV
  Access staffer must add you to the approved-submitters list for this ID. This
  can take **up to 2 weeks**. You (the repo maintainer) don't need to do
  anything except wait after submitting.
- No human code/security audit is required, but the add-on must follow the
  [NVDA Code of Conduct](https://github.com/nvaccess/nvda/blob/master/CODE_OF_CONDUCT.md).

## Before you submit — validate locally

1. **Install and test on your NVDA.** Install the `.nvda-addon` from the v1.0.0
   release (or Downloads) via *NVDA menu → Tools → Add-on Store → Install from
   external file*. Open each feature (Tools → Sarvam AI) and confirm it speaks
   and works with your funded API key. The store's `lastTestedVersion` claims
   compatibility up to NVDA 2026.1 — verify it runs on your NVDA version.
2. Make sure the **release asset URL stays valid forever** (GitHub release URLs
   do). Do not delete the v1.0.0 release.

## Submit

1. Open the **Add-on registration issue form**:
   <https://github.com/nvaccess/addon-datastore/issues/new?template=registerAddon.yml>
2. Enter the values below.
3. Submit. Wait for the automated checks and (first time) approval.

## Exact field values for the issue form

| Field | Value |
|---|---|
| Add-on ID | `sarvamAI` |
| Display name | `Sarvam AI assistant` |
| Publisher | `Rakesh Honisty` |
| Channel | `stable` |
| Add-on version name | `1.0.0` |
| Version number | major `1`, minor `0`, patch `0` |
| Download URL | `https://github.com/rakeshhonisty/Sarvam-AI-assistant/releases/download/v1.0.0/SarvamAIassistant-1.0.0.nvda-addon` |
| SHA256 | `008cb6aa846f9ff155ddc3d219e888c8e560d5d3b91ff22bf5e064052747a8bd` |
| Homepage | `https://github.com/rakeshhonisty/Sarvam-AI-assistant` |
| Source URL | `https://github.com/rakeshhonisty/Sarvam-AI-assistant` |
| Minimum NVDA version | `2021.1` |
| Last tested NVDA version | `2026.1` |
| License | `GPL v2` |
| License URL | `https://www.gnu.org/licenses/old-licenses/gpl-2.0.html` |

> The form auto-reads most of these from the add-on manifest inside the
> `.nvda-addon`; the values above already match the manifest, so validation
> (which cross-checks manifest vs. form) will pass.

## Generated metadata (reference)

The JSON the bot will produce is mirrored here for reference:
[`sarvamAI-1.0.0.json`](./sarvamAI-1.0.0.json). You do **not** submit this file
directly — the issue form generates it.

## If validation fails

- Read the automated comment on the PR/issue.
- Common causes: manifest field mismatch, invalid `minimumNVDAVersion` /
  `lastTestedNVDAVersion` (must be exact entries in NV Access's
  `nvdaAPIVersions.json`), or a VirusTotal flag (usually a false positive on the
  bundled `.pyc`-free source; reply explaining it, or email info@nvaccess.org).
- Fix the manifest (edit `buildVars.py`), run `python build.py`, upload the new
  `.nvda-addon` to a new release, and **re-submit the issue form** with the new
  URL and SHA256.

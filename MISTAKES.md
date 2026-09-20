# Failure Log (MISTAKES.md)

This log records unexpected failures, broken contracts, or user corrections across the Antigravity engineering environment. Entries are prepended chronologically.

Per Rule 10 of the Antigravity Constitution, each entry must contain the following four mandatory fields:
1. **Date & Incident:** Summary of what broke.
2. **Root Cause:** What flawed assumption or missing validation triggered the defect?
3. **Impact:** What was disrupted or regressed?
4. **Preventive Invariant:** Concrete rule or automated guard to prevent recurrence.

*(Any failure pattern occurring 3 times must be promoted to permanent constitutional rules.)*

---

<!-- Entries are prepended below this line -->

### 2026-09-20 - YouTube Stream Download HTTP 403 Forbidden
* **Date & Incident:** 2026-09-20 - Video stream download failed with `HTTP Error 403: Forbidden` on Railway.
* **Root Cause:** Overriding `GVS_PO_TOKEN_POLICY.required = False` in `universal_patch.py` caused yt-dlp to select iOS video formats which YouTube's video CDN rejects without a valid PO token. Additionally, passing residential cookies to mobile stream endpoints caused session-IP mismatches.
* **Impact:** YouTube downloads succeeded at the metadata extraction phase but failed during binary stream downloading on Railway.
* **Preventive Invariant:** Never relax upstream PO Token requirements unless verified end-to-end with an actual multi-megabyte stream download. Prioritize `visionos` which does not require a GVS PO token, and automatically retry without cookies if 403 Forbidden is encountered.

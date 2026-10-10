# Untracked files cleanup U1–U4 — execution receipt

User 22735 "All" → U1–U4 of proposal r2 (240b814) + r2.1 (a5be502), codex PASS 22725. Zero deletions. Not pushed.

- Pre-change tests (HEAD a5be502): hygiene 6 passed, P2G 13 passed (`pre-*.log`, EXIT_STATUS=0).
- `untracked-cleanup-u1-u4-verify-and-stage.py` → `verify-and-stage-receipt.json`: STAGED_OK.
  codex review seal OK; 2+118+142+1,197 files match path/size/sha256 (U3 binaries hashed in full); `.gitignore`
  got one marked section with codex's 142 U3 + 265 U4 exact rules verbatim; staged set = expected exactly
  (1,342 added + `.gitignore` modified; 36,053,921 B new).
- Commit **5dc7c34**. After it: tracked tree clean; only this receipt dir untracked (then committed itself).
- Retention (`post-commit-retention-check.json`): U3 142/142 present, same size, git-ignored; U4 265/265 roots and
  27,424/27,424 catalog files present, same size (853,613,163 B).
- Post-change tests: hygiene 6 passed, P2G 13 passed (`post-*.log`, EXIT_STATUS=0).
- Untouched: Q3/Q4/Q5 Modal storage, worktree weights, shared HF cache, all historical seals.

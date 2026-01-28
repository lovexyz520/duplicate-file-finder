# Duplicate File Finder - Task Tracker

Last updated: 2026-01-28

## Done
- [x] Core module extraction (scanner/dupe/actions/report/types)
- [x] 3-layer matching (size -> partial hash -> full hash)
- [x] CLI additions: --report, --partial-size-mb, --full-hash
- [x] Strategy controls: --keep-strategy, --prefer-path, --move-scope
- [x] Strategy preview summary + clearer preview lists
- [x] Naming cleanup options (copy suffix/space/special + conflict suffix)
- [x] CSV report includes action/strategy/keep/move + conflict fields
- [x] Documentation updates (README/CLAUDE)
- [x] Tag and release prep: v1.1.0
- [x] Work-file organizer CLI + presets + time partitioning + duplicates quarantine

## Next up
- [ ] Streamlit UI (preview -> confirm -> execute)
- [ ] Unit tests for core modules
- [ ] Permission error test harness (Windows ACL/SID)

## Optional/Backlog
- [ ] Release notes and version bump (v1.2.0)

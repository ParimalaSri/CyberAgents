# accounts layer checks (contract `context/contracts/accounts.yml`, extra `scripts/check_accounts_extra.py`)

Run from the repo root:
- `python .claude/skills/data-quality-check/scripts/check_contract.py context/contracts/accounts.yml --report`
- `python .claude/skills/data-quality-check/scripts/check_accounts_extra.py` (exit 1 on any failure; prints the author-versus-mine table)
- tests: `python -m unittest discover -s .claude/skills/data-quality-check/scripts -p "test_check_accounts*.py"` (47 injected faults)

Conventions the checks encode (D9.6 to D9.9, D10):
- The recompute uses its own constants block (PROVISIONAL points, FLOOR 0.5, X 40, Y 20); change it together with the contract's three PROVISIONAL checks when calibration lands.
- Excluded account: `band_uncapped = band = 'exclude'`, `cap_reasons` null, `top_signals` null, honeypot `why`.
- `top_signals` is null when `urgency_score = 0` (even if fit is above 0) and for excluded accounts; otherwise the two largest-point signals (vulnerability, exposure, hygiene, fit on ties); one signal is tolerated on a would-be contact when the `why` would pass 40 words.
- `cap_reasons`: alphabetical (DQ-012). `why`: at most one cap clause; the precedence seen is operator_name_shape, singleton, low_confidence (not asserted).
- Phrase table (matched by pattern; every phrase must be true and correctly numbered in signals): KEV host count, "worst vulnerability scores CVSS x.y", "an exposed admin or database service (...) on outdated software", "remote-admin or database services exposed (...)", "SSH (port 22) open to the internet", end-of-life, expired certificates, old TLS, "N IPs in the footprint", "hosts located in CC", "database, medical or IoT systems in the stack"; closing "Exposure is limited." only on skip accounts with urgency above 0 (DQ-013).
- M3 relaxes the checks marked "M2 only" in the contract (decision and prompt_version null, final_band = band, the operator_unverified iff rule); they become D9.9 rule 6.
- Not checkable here: that the constants are right (the recompute proves the rules were applied), operator names the flag misses (DQ-009, DQ-014), a rerun giving an identical file (needs the stage to write data).

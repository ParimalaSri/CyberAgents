# accounts extra checks after D12 (2026-10-11, sample, check_accounts_extra.py)

**PASS**: 7/7 extra checks passed

| result | check | evidence |
|---|---|---|
| PASS | accounts rows == signals rows == companies rows, account_id unique and non-null, id sets equal both ways | accounts 5,790, signals 5,790, companies 5,790, duplicate ids 0, only in accounts 0, only in signals 0 |
| PASS | independent recompute of fit, urgency, contact, band_uncapped, cap_reasons, band, top_signals from signals: 0 disagreements | 5,790 accounts; missing 0, extra 0; column disagreements none; examples []; one-signal fallback applied on 8 accounts and equal to my recomputation (two-signal why over 40 words); operator_name_shape differs from T1 or T2 on 0 signal rows |
| PASS | review cut (D11.2, N = 200, floor 20): band size, cut score, tie size, tied accounts kept and order of skip versus review equal my recomputation | review 200 (expected 200), would-be 51, top-N only 149, cut score 30, tie 142, kept 7, to skip 135; differences from mine none; skip accounts ranked above the weakest review account 0 []; flagged accounts kept at the cut over an unflagged one 0 [] |
| PASS | why on every account: non-empty, at most 40 words, no '=' or '_', no breach words, D10 clause exactly on would-be contacts, every phrase true and correctly numbered in signals, named signals equal top_signals, cap clause matches cap_reasons, nothing unrecognised | 5,790 accounts checked; problems none; examples [] |
| PASS | file order is contact_score desc, urgency_score desc, operator_name_shape asc (false first), coalesce(kev_host_count, 0) desc, host_count desc, account_id asc (D12.1) | 0 adjacent pairs out of order; first at row none |
| PASS | denylist leakage in company_name (shared rules, org text) | 0 hits; none |
| PASS | score bounds, contact <= urgency, FLOOR invariant, band set, final_band = band, no contact before adjudication, decision null, cap_reasons order | 0 violations; none |

## Author versus independent recomputation

| quantity | author | mine | match |
|---|---|---|---|
| rows | 5790 | 5790 | yes |
| contact | 0 | 0 | yes |
| review | 200 | 200 | yes |
| skip | 5589 | 5589 | yes |
| exclude | 1 | 1 | yes |
| would_be_contacts | 51 | 51 | yes |
| urgency_above_0 | 1324 | 1324 | yes |
| fit_above_0 | 1190 | 1190 | yes |
| max_fit | 65 | 65 | yes |
| cut_score | 30 | 30 | yes |
| tie_size | 142 | 142 | yes |
| tie_kept | 7 | 7 | yes |
| tie_to_skip | 135 | 135 | yes |
| accounts_above_cut | 193 | 193 | yes |
| top_n_only | 149 | 149 | yes |
| review_operator_shaped | 35 | 35 | yes |
| review_operator_via_cap | 5 | 5 | yes |
| review_operator_via_top_n | 30 | 30 | yes |
| review_singletons | 27 | 27 | yes |
| review_low_confidence | 8 | 8 | yes |
| skip_urgency_above_0 | 1123 | 1123 | yes |
| skip_below_floor | 659 | 659 | yes |
| skip_below_floor_non_ssh | 42 | 42 | yes |
| skip_below_floor_cvss7 | 32 | 32 | yes |
| skip_below_floor_overlap | 0 | 0 | yes |
| skip_below_floor_union | 74 | 74 | yes |
| skip_beyond_cut | 464 | 464 | yes |
| skip_signal_clause | 537 | 537 | yes |
| skip_signal_clause_kev | 303 | 303 | yes |
| skip_signal_clause_cvss | 234 | 234 | yes |
| skip_signal_clause_at_or_above_floor | 455 | 455 | yes |
| skip_signal_clause_below_floor | 82 | 82 | yes |
| skip_plain_clause | 586 | 586 | yes |
| exposure_phrase_accounts | 40 | 40 | yes |
| longest_why_words | 40 | 40 | yes |
| longest_skip_why_words | 33 | 33 | yes |
| union_fit_lost | 66 | 66 | yes |
| union_contact_changed | 29 | 29 | yes |
| kept_tied_flagged | 0 | 0 | yes |
| review_operator_shaped_d11 | 42 | 42 | yes |
| cap set operator_unverified | 46 | 46 | yes |
| cap set operator_name_shape,operator_unverified | 4 | 4 | yes |
| cap set operator_name_shape,operator_unverified,singleton | 1 | 1 | yes |

## Other recomputed numbers (mine)

- rows: 5790
- contact: 0
- review: 200
- skip: 5589
- exclude: 1
- would_be_contacts: 51
- urgency_above_0: 1324
- fit_above_0: 1190
- max_fit: 65
- cut_score: 30
- tie_size: 142
- tie_kept: 7
- tie_to_skip: 135
- accounts_above_cut: 193
- top_n_only: 149
- review_operator_shaped: 35
- review_operator_via_cap: 5
- review_operator_via_top_n: 30
- review_singletons: 27
- review_low_confidence: 8
- skip_urgency_above_0: 1123
- skip_below_floor: 659
- skip_below_floor_non_ssh: 42
- skip_below_floor_cvss7: 32
- skip_below_floor_overlap: 0
- skip_below_floor_union: 74
- skip_beyond_cut: 464
- skip_beyond_cut_non_ssh: 9
- skip_beyond_cut_cvss7: 441
- skip_beyond_cut_union: 450
- longest_why_words: 40
- longest_why_words_recount: 40
- longest_skip_why_words: 33
- skip_signal_clause: 537
- skip_signal_clause_kev: 303
- skip_signal_clause_cvss: 234
- skip_signal_clause_at_or_above_floor: 455
- skip_signal_clause_below_floor: 82
- skip_plain_clause: 586
- skip_signal_clause_in_file: 537
- skip_plain_clause_in_file: 586
- exposure_phrase_accounts: 40
- exposure_phrase_accounts_in_file: 40
- exposure_old_phrase_in_file: 0
- exposure_top_two_before_fallback: 48
- fallback_accounts: 8
- fallback_dropped_exposure: 8
- kept_tied_flagged: 0
- review_operator_shaped_d11: 42
- union_fit_lost: 66
- union_contact_changed: 29
- max_scores: {'fit_score': 65, 'urgency_score': 100, 'contact_score': 68}
- cap sets: {'operator_unverified': 46, 'operator_name_shape,operator_unverified': 4, 'operator_name_shape,operator_unverified,singleton': 1}

## What D12.1 moved (my recomputation against the D11 order)

- kept at the cut (7): ['Alta Gracia Project Holding Ltd', 'Provider Ktechnology', 'Brainoza OU', 'SugarHosts', 'Seiko Electric Co.,Ltd.', 'Free Way Tecnologia', 'Owl Limited']; author's: ['Alta Gracia Project Holding Ltd', 'Provider Ktechnology', 'Brainoza OU', 'SugarHosts', 'Seiko Electric Co.,Ltd.', 'Free Way Tecnologia', 'Owl Limited']; equal: True
- left review (7): ['CSLOXINFO-IDC', 'GCI Network Solutions Limited', 'NTT PC Communications, Inc.', 'The Infrastructure Group B.V.', 'Zen Internet Ltd', 'Zillion Network Inc', 'Ziply Fiber']; author's: ['CSLOXINFO-IDC', 'GCI Network Solutions', 'NTT PC Communications', 'The Infrastructure Group', 'Zen Internet', 'Zillion Network', 'Ziply Fiber']; equal: True (equal after the author's trimmed legal suffixes)
- entered review (7): ['Alta Gracia Project Holding Ltd', 'Brainoza OU', 'Free Way Tecnologia', 'Owl Limited', 'Provider Ktechnology', 'Seiko Electric Co.,Ltd.', 'SugarHosts']
- top 25 by the total order: same set as under the D11 order False; positions that differ 7
- fit_score quantiles (linear): p5 0.00, p25 0.00, p50 0.00, p75 0.00, p90 15.00, p95 15.00, p99 30.00
- urgency_score quantiles (linear): p5 0.00, p25 0.00, p50 0.00, p75 0.00, p90 40.00, p95 60.00, p99 65.00
- contact_score quantiles (linear): p5 0.00, p25 0.00, p50 0.00, p75 0.00, p90 23.00, p95 30.00, p99 39.00

## Alarm or reassurance words in why (report only, 1 hits)

- SC Lithuanian Radio and TV Center: attack

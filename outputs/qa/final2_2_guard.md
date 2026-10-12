# Final2 G2: guard re-attack against the allowlist guard (scripts/path_guard.py at 10e75fa)

## Method and safety
- Every case is built over a SCRATCH ANALOG (`scratchpad/g2/an`, `scratchpad/g2/an2`: folders `data/raw`, `Cyber_DataSet`, siblings, on C: inside the scratchpad). Asserts before any write: the analog paths resolve inside the scratchpad. The guard is called as `forbidden_reason(path, dataset_dir=<analog>, raw_dir=<analog>)`; the real constants are not used, so no string in this file was checked against or written to D:/Cyber_DataSet or the real data/raw.
- The OS oracle writes `x.parquet` through the variant and checks whether it landed in the analog protected folder. FAIL = the guard allows a path that reaches the analog folder (or a refusal expectation is not met).
- `pg/pg_break.py` was read: it only calls the guard and `realpath`; but it aims at the real folders and uses two junctions in the scratchpad that point at the real dataset and raw folders (`scratchpad/pg/dslink`, `rawlink`). I did NOT run it; I re-wrote the 26 cases on the analog (`g2/g2_cases.py`). Those two old junctions still exist in the scratchpad (not touched; the owner may want to remove them with `rmdir`, never a recursive delete).
- Not run: file or directory symlinks (`mklink` needs a privilege: refused). Hard link was possible and is reported as INFO.

## 1a. The 26 old cases (`pg_break.py`, mapped to the analog; row 18 is the drive-relative case, now always refused as `drive-relative`)

| name | expect | guard | os | result |
|---|---|---|---|---|
| 01 plain data/raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| 02 dotdot | refuse | REFUSED | reaches: file landed in analog | PASS |
| 03 upper case | refuse | REFUSED | reaches: file landed in analog | PASS |
| 05 trailing dot dir | refuse | REFUSED | reaches: file landed in analog | PASS |
| 06 trailing space dir | refuse | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 07 extended prefix | refuse | REFUSED | reaches: file landed in analog | PASS |
| 08 UNC admin share raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| 09 junction to data/raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| 10 dataset folder | refuse | REFUSED | reaches: file landed in analog | PASS |
| 11 dataset upper+dotdot | refuse | REFUSED | reaches: file landed in analog | PASS |
| 12 dataset via junction | refuse | REFUSED | reaches: file landed in analog | PASS |
| 13 dataset UNC | refuse | REFUSED | reaches: file landed in analog | PASS |
| 14 dataset trailing dot | refuse | REFUSED | reaches: file landed in analog | PASS |
| 15 data//raw doubled sep | refuse | REFUSED | reaches: file landed in analog | PASS |
| 16 ADS data/raw::$DATA | refuse | REFUSED | no reach: open failed: OSError | PASS |
| 17 8.3 short name RAW~1 (nonexistent) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| 19 bare dataset dir | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| 20 sibling data/raw2 (must allow) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| 21 data/silver (must allow) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| 22 sibling Cyber_DataSet2 (must allow) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| 23 data/raw copy elsewhere (policy) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| 24 trailing space dataset dir | refuse | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 25 report path under raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| 26 empty string | allow | allowed | no reach: no oracle (guard-only) | PASS |
| 04 relative data/raw (cwd=analog root) | refuse | REFUSED | reaches: file landed in analog | PASS |
| 18 drive-relative C:an2/Cyber_DataSet (cwd=parent of analog) | refuse | REFUSED | reaches: file landed in analog | PASS |

## 1b. The 79 earlier cases (`final_2_guard.md`, including the 7 that failed last time: rows 31, 32, 33, 36, 38, 51, 52)

| n | name | guard | os | result |
|---|---|---|---|---|
| 1 | RAW mixed separators | REFUSED | reaches: file landed in analog | PASS |
| 2 | RAW doubled separators | REFUSED | reaches: file landed in analog | PASS |
| 3 | RAW doubled backslashes | REFUSED | reaches: file landed in analog | PASS |
| 4 | RAW device ns . | REFUSED | reaches: file landed in analog | PASS |
| 5 | RAW fwdslash ext //?/ | REFUSED | reaches: file landed in analog | PASS |
| 6 | RAW NT prefix ?? | REFUSED | reaches: file landed in analog | PASS |
| 7 | RAW GLOBALROOT | REFUSED | reaches: file landed in analog | PASS |
| 8 | RAW Volume{GUID} | REFUSED | reaches: file landed in analog | PASS |
| 9 | RAW UNC 127.0.0.2 C$ | REFUSED | no reach: open failed: OSError | PASS |
| 10 | RAW UNC localhost. C$ | REFUSED | no reach: open failed: OSError | PASS |
| 11 | RAW UNC ipv6-literal | REFUSED | reaches: file landed in analog | PASS |
| 12 | RAW UNC machine fqdn | REFUSED | reaches: file landed in analog | PASS |
| 13 | RAW UNC own LAN ip | REFUSED | reaches: file landed in analog | PASS |
| 14 | RAW 8.3 short name C:\Users\sikha\AppData\Local\Temp\claude\D--CYB~3\B020CB~1\SCRATC~1\g2\an\data\raw | REFUSED | reaches: file landed in analog | PASS |
| 15 | RAW ADS ::$DATA on file | REFUSED | reaches: file landed in analog | PASS |
| 16 | RAW dir trailing dot | REFUSED | reaches: file landed in analog | PASS |
| 17 | RAW dir trailing space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 18 | RAW dir trailing dot+space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 19 | RAW dir trailing NBSP | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 20 | RAW dir trailing ZWSP | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 21 | RAW every part trailing dot | REFUSED | reaches: file landed in analog | PASS |
| 22 | RAW every part trailing space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 23 | RAW fullwidth names | allowed | no reach: open failed: FileNotFoundError | PASS |
| 24 | RAW dir:$I30:$INDEX_ALLOCATION/x | REFUSED | reaches: file landed in analog | PASS |
| 25 | RAW dir::$INDEX_ALLOCATION/x | REFUSED | reaches: file landed in analog | PASS |
| 26 | DS mixed separators | REFUSED | reaches: file landed in analog | PASS |
| 27 | DS doubled separators | REFUSED | reaches: file landed in analog | PASS |
| 28 | DS doubled backslashes | REFUSED | reaches: file landed in analog | PASS |
| 29 | DS device ns . | REFUSED | reaches: file landed in analog | PASS |
| 30 | DS fwdslash ext //?/ | REFUSED | reaches: file landed in analog | PASS |
| 31 | DS NT prefix ?? | REFUSED | reaches: file landed in analog | PASS |
| 32 | DS GLOBALROOT | REFUSED | reaches: file landed in analog | PASS |
| 33 | DS Volume{GUID} | REFUSED | reaches: file landed in analog | PASS |
| 34 | DS UNC 127.0.0.2 C$ | REFUSED | no reach: open failed: OSError | PASS |
| 35 | DS UNC localhost. C$ | REFUSED | no reach: open failed: OSError | PASS |
| 36 | DS UNC ipv6-literal | REFUSED | reaches: file landed in analog | PASS |
| 37 | DS UNC machine fqdn | REFUSED | reaches: file landed in analog | PASS |
| 38 | DS UNC own LAN ip | REFUSED | reaches: file landed in analog | PASS |
| 39 | DS 8.3 short name C:\Users\sikha\AppData\Local\Temp\claude\D--CYB~3\B020CB~1\SCRATC~1\g2\an\CYBER_~1 | REFUSED | reaches: file landed in analog | PASS |
| 40 | DS ADS ::$DATA on file | REFUSED | reaches: file landed in analog | PASS |
| 41 | DS dir trailing dot | REFUSED | reaches: file landed in analog | PASS |
| 42 | DS dir trailing space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 43 | DS dir trailing dot+space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 44 | DS dir trailing NBSP | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 45 | DS dir trailing ZWSP | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 46 | DS every part trailing dot | REFUSED | reaches: file landed in analog | PASS |
| 47 | DS every part trailing space | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 48 | DS fullwidth names | allowed | no reach: open failed: FileNotFoundError | PASS |
| 49 | DS dir:$I30:$INDEX_ALLOCATION/x | REFUSED | reaches: file landed in analog | PASS |
| 50 | DS dir::$INDEX_ALLOCATION/x | REFUSED | reaches: file landed in analog | PASS |
| 51 | RAW ADS :evil on folder | REFUSED | reaches: stream created on the analog folder | PASS |
| 52 | DS ADS :evil on folder | REFUSED | reaches: stream created on the analog folder | PASS |
| 53 | RAW junction | REFUSED | reaches: file landed in analog | PASS |
| 54 | RAW junction chain j2->j1->target | REFUSED | reaches: file landed in analog | PASS |
| 55 | RAW symlink dir | - | -: NOT RUN: mklink /D refused: You do not have sufficient privilege to perform this operation. | NOT RUN |
| 56 | RAW abs: junction then .. .. then protected | REFUSED | reaches: file landed in analog | PASS |
| 57 | RAW relative cwd=deep via junction and .. | REFUSED | reaches: file landed in analog | PASS |
| 58 | RAW relative bare name, cwd=protected | REFUSED | reaches: file landed in analog | PASS |
| 59 | RAW relative ./x, cwd=protected | REFUSED | reaches: file landed in analog | PASS |
| 60 | DS junction | REFUSED | reaches: file landed in analog | PASS |
| 61 | DS junction chain j2->j1->target | REFUSED | reaches: file landed in analog | PASS |
| 62 | DS symlink dir | - | -: NOT RUN: mklink /D refused: You do not have sufficient privilege to perform this operation. | NOT RUN |
| 63 | DS abs: junction then .. .. then protected | REFUSED | reaches: file landed in analog | PASS |
| 64 | DS relative cwd=deep via junction and .. | REFUSED | reaches: file landed in analog | PASS |
| 65 | DS relative bare name, cwd=protected | REFUSED | reaches: file landed in analog | PASS |
| 66 | DS relative ./x, cwd=protected | REFUSED | reaches: file landed in analog | PASS |
| 67 | RAW literal %CD%/data/raw | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 68 | RAW long 360 chars then .. back | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 69 | RAW 250-char dir then .. | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 70 | DS ~40k chars then .. back | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 71 | DS 5000-char component | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| 72 | odd string '' | allowed | n/a: no analog; guard behaviour only | INFO |
| 73 | odd string ' ' | REFUSED | n/a: no analog; guard behaviour only | INFO |
| 74 | odd string '.' | allowed | n/a: no analog; guard behaviour only | INFO |
| 75 | odd string '..' | allowed | n/a: no analog; guard behaviour only | INFO |
| 76 | odd string 'x\x00y' | REFUSED | n/a: no analog; guard behaviour only | INFO |
| 77 | odd string 'D:' | REFUSED | n/a: no analog; guard behaviour only | INFO |
| 78 | odd string 'CON' | allowed | n/a: no analog; guard behaviour only | INFO |
| 79 | odd string 'NUL' | allowed | n/a: no analog; guard behaviour only | INFO |

79-case counts: INFO 8, NOT 2, PASS 69. The 7 earlier FAIL rows (NT prefix, GLOBALROOT, Volume GUID, ipv6-literal UNC, own-LAN-IP UNC, ADS on both folders) are now REFUSED and each still reaches the analog through the OS, so the refusal is what protects.

## 2. 50 new cases (none in an earlier list)

| name | expect | guard | os | result |
|---|---|---|---|---|
| N01 lower-case drive letter c:/.. | refuse | REFUSED | reaches: file landed in analog | PASS |
| N02 upper-case drive letter C:/.. (control) | refuse | REFUSED | reaches: file landed in analog | PASS |
| N03 forward-slash folder with trailing separators (path = folder) | refuse | REFUSED | reaches: samefile folder | PASS |
| N04 DS/./x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N05 DS//x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N06 DS/../Cyber_DataSet/x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N07 RAW/../raw/x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N08 junction chain of 4 to dataset analog | refuse | REFUSED | reaches: file landed in analog | PASS |
| N09 junction to the analog PARENT then child Cyber_DataSet/x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N10 junction to analog parent then data/raw/x | refuse | REFUSED | reaches: file landed in analog | PASS |
| N11 junction to parent, child via .. out and back | refuse | allowed | no reach: open failed: FileNotFoundError | FAIL (expectation error; judged PASS, see below) |
| N12 file symlink | - | - | NOT RUN: You do not have sufficient privilege to perform this operation. | NOT RUN |
| N13 hard link outside to a file inside dataset analog | either | allowed | reaches: write through hard link changed the protected file's content (file-level alias; out of the folder-level policy) | INFO |
| N14 path equal to protected folder (dataset) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N15 path equal to protected folder (raw) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N16 path equal to its parent (analog data/) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| N17 path equal to grandparent (analog root) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| N18 reserved device CON inside dataset analog | either | REFUSED | no reach: device name; nothing opened, no file in folder | PASS |
| N18 reserved device NUL inside dataset analog | either | allowed | no reach: device name; nothing opened, no file in folder | PASS |
| N18 reserved device AUX inside dataset analog | either | REFUSED | no reach: device name; nothing opened, no file in folder | PASS |
| N19 reserved name bare CON | either | allowed | no reach: no oracle (guard-only) | PASS |
| N20 reserved name CON.txt in dataset analog | either | REFUSED | no reach: device alias; nothing opened | PASS |
| N21 8.3 alias of dataset analog (C:\Users\sikha\AppData\Local\Temp\claude\D--CYB~3\B020CB~1\SCRATC~1\g2\an2\CYBER_~1) | refuse | REFUSED | reaches: file landed in analog | PASS |
| N22 8.3 alias of analog root + longname child | refuse | REFUSED | reaches: file landed in analog | PASS |
| N23 UNC localhost C$ style to dataset | refuse | REFUSED | reaches: file landed in analog | PASS |
| N24 UNC localhost C$ style to raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| N25 leading single slash /Cyber_DataSet/x vs dataset_dir=<cwd drive>:/Cyber_DataSet/ (pure check, cwd drive C:) | refuse | REFUSED | guard-only (resolves against the cwd drive root) | PASS |
| N26 leading single slash /data/raw/x (any data/raw pair) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N27 270-char name under dataset analog | refuse | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| N28 33,000-char path via a/.. repeats back into dataset analog | refuse | REFUSED | no reach: open failed: FileNotFoundError | PASS |
| N29 long s (U+017F) in DataSet | either | allowed | no reach: open failed: FileNotFoundError | PASS |
| N30 NFD-normalised analog path (ASCII: identical) | refuse | REFUSED | reaches: file landed in analog | PASS |
| N31 fullwidth dataset name | either | allowed | no reach: open failed: FileNotFoundError | PASS |
| N32 Data/Raw mixed case | refuse | REFUSED | reaches: file landed in analog | PASS |
| N33 data/./raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| N34 data//raw | refuse | REFUSED | reaches: file landed in analog | PASS |
| N35 backslash DATA RAW | refuse | REFUSED | reaches: file landed in analog | PASS |
| N36 tilde home form ~/Cyber_DataSet/x | either | allowed | no reach: no oracle (guard-only) | PASS |
| N37 tilde 8.3 style CYBER~1 (nonexistent sibling) | either | allowed | no reach: no oracle (guard-only) | PASS |
| N38 embedded newline in analog path | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N39 embedded tab in analog path | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N40 dot (cwd = repo, no data/raw match) | either | allowed | no reach: no oracle (guard-only) | PASS |
| N41 dot-dot (cwd = repo) | either | allowed | no reach: no oracle (guard-only) | PASS |
| N42 dot with cwd = dataset analog (path is the folder) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N43 empty string with cwd = dataset analog | either | REFUSED | no reach: no oracle (guard-only) | PASS |
| N44 dot-dot with cwd = dataset analog/sub (is the folder) | refuse | REFUSED | no reach: no oracle (guard-only) | PASS |
| N45 ../x.parquet with cwd = dataset analog/sub | refuse | REFUSED | reaches: file landed in analog | PASS |
| N46 empty string (cwd = repo) | either | allowed | no reach: no oracle (guard-only) | PASS |
| N47 DEL (0x7f) in name | either | REFUSED | reaches: file landed in analog | PASS |
| N48 trailing backslash dataset folder (path = folder) | refuse | REFUSED | reaches: samefile folder | PASS |
| N49 sibling Cyber_DataSet_ (must allow) | allow | allowed | no reach: no oracle (guard-only) | PASS |
| N50 sibling data/rawx (must allow) | allow | allowed | no reach: no oracle (guard-only) | PASS |

## Counts
old 26: {'PASS': 26}; new 50: {'PASS': 49, 'FAIL': 1, 'NOT RUN': 1, 'INFO': 1}.

### Judgement on the single FAIL row (N11)
N11 `<analog>/other/jp/../Cyber_DataSet/x.parquet` where `jp` is a junction to the analog root: expectation was wrong, not the guard. Win32 collapses `..` lexically before following any junction (`jp/..` is `other`), so the OS opened `other/Cyber_DataSet/x.parquet` (open failed: no such folder, no reach). The guard's `abspath` collapses it the same way and allows it. The oracle in the same row measured reach = none. Judged PASS (expectation error); no path to a protected folder.

### INFO: hard link (N13)
A file hard link that exists OUTSIDE the protected folder and shares a file with one inside it lets a write through the link change the protected file's content; the guard allows it (it compares directory objects, ancestors only, never the target file). Out of the stated policy (folder-level, and creating the link needs a prior write or `mklink /H` by the same user), and the stages write new files via `COPY ... TO` / `write_parquet`; I record it as a known limit, Low, not a FAIL. A fix would be `samefile` on the target when it exists against files inside the folders (cheap), or refusing `st_nlink > 1`.

### Observations on the allowlist logic itself (read of `path_guard.py`)
- Order is right: the plain-path allowlist runs before any resolution; anything unusual is refused rather than rewritten. `samefile` over every existing ancestor closes junction/8.3/case aliases (N08, N09, N21, N22 reach the analog and are refused).
- A refused spelling never needs the OS to agree: `\localhost\C$`, ipv6-literal, own LAN IP, GLOBALROOT, Volume GUID, `\??\`, device namespace are all refused by the single leading double-slash rule, including spellings I did not try.
- `forbidden_reason('')`, `'.'` and `'..'` are allowed when the cwd is not protected, and refused when the cwd is the protected folder (N42, N43, N44: the guard resolves them against the cwd).
- `CON`, `NUL`, `AUX` (bare or inside the analog) are allowed: the OS writes to the device, nothing lands in a folder (no reach).
- `~/x` is not expanded by Python or Windows (relative name `~` under the cwd); no code path expands it (`grep expanduser|expandvars` in `pipeline/` and `scripts/`: no matches).
- Leading single slash `/Cyber_DataSet/x` resolves against the cwd drive (N25: refused when the constant's drive equals the cwd drive; N26 `/data/raw/x` refused by the part-pair clause). If the cwd is on another drive than D:, `/Cyber_DataSet/x` resolves to that drive: not the dataset folder, correct.
- Long names: a 270-char component and 33,000-char `a/..` chains do not reach (OS error) and the guard refuses them anyway (resolves under the analog).

## 3. Legit uses still allowed (guard only, constants: real raw folder = repo `data/raw`, dataset constant = the scratch analog)

| Path | Guard |
|---|---|
| `data/silver/x.parquet` | allowed |
| `data/gold/x.parquet` | allowed |
| `D:/CyberAgents/data/silver/hosts.parquet` | allowed |
| `D:/CyberAgents/outputs/qa/x.md` | allowed |
| `outputs/dq/x.md` | allowed |
| `C:/Users/sikha/AppData/Local/Temp/x.parquet` | allowed |
| `C:/Users/sikha/AppData/Local/Temp/sub dir/x.parquet (space inside a name)` | allowed |
| `scratchpad/g2/legit.parquet (absolute, backslashes)` | allowed |

`--output` to a scratch file through each stage's CLI: see `final2_4_determinism.md` (all four stages wrote to scratch; the sample builder is covered by `test_path_guard`).
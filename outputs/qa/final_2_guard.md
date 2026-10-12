# Final F2: path guard re-attack (`scripts/path_guard.py`, committed 05eeb10)

## Method and safety
- `pg/pg_break.py` read first: it only calls `forbidden_reason(string)`, `os.path.realpath/abspath` and (originally) `mklink /J` plus `os.path.exists` on two junctions in the scratchpad. I ran a copy `pg/pg_break_final.py` with the `mklink` and `exists` lines removed (the two junctions already existed in the scratchpad: `rawlink` to `data/raw`, `dslink` to the dataset folder). It writes nothing. The guard's own `realpath` on a dataset-folder string does a path lookup of that folder (read-only metadata); that is inherent to calling the guard and is the same lookup a stage makes.
- New cases (`pg2/final_pg.py`): every variant is built over a SCRATCH ANALOG (`scratchpad/pg2/an/data/raw` and `an/Cyber_DataSet`, on the C: drive inside the scratchpad). The guard is called through `forbidden_reason(path, dataset_dir=<analog>, raw_dir=<analog>)`. The OS oracle writes `x.parquet` through the variant string and checks whether the file landed in the analog protected folder (only scratch is ever written). FAIL = the OS reaches the analog folder and the guard allows the string. A separate section calls the guard with the real constants on strings only (no write), using the real D: device name (`\Device\HarddiskVolume5`) and volume GUID read with `QueryDosDevice` and `GetVolumeNameForVolumeMountPoint` (mount-point queries, nothing in the folder).
- Not run: symlinks (`mklink /D` refused: "You do not have sufficient privilege"); only junctions were tested, and a junction-to-junction chain.

## 1. The 26 old cases (`pg_break_final.py`, cwd = scratchpad on C:)
26 of 26 PASS under the harness's own expectations (the same script printed 25 PASS and 1 FAIL, row 18, when it was run from `D:\CyberAgents`; see below). Row 17 (`RAW~1`, a name that does not exist) is allowed, as expected. Rows 06, 07 and 24 resolve to a `\\?\D:\...` string through `realpath` and are refused.

### Row 18 (drive-relative `D:Cyber_DataSet/x`): my judgement
The data-engineer is right that the harness expectation was wrong for the case it failed on. Measured with the committed guard (`pg2/row18.py`):

| cwd of the process | `Path("D:Cyber_DataSet/x").resolve()` | guard |
|---|---|---|
| `D:\CyberAgents` | `D:\CyberAgents\Cyber_DataSet\x` | allowed (correct: that is not the dataset folder) |
| `D:\` | `D:\Cyber_DataSet\x` | refused |
| `C:\Users` (no per-drive cwd for D:, `=D:` unset) | `D:\Cyber_DataSet\x` | refused |

Windows resolves a drive-relative path against the per-drive current directory, and `abspath` (GetFullPathName) uses the same rule as the write call in the same process, so the guard and the writer agree. I also checked the writer side: DuckDB `COPY ... TO 'C:sub/a.parquet'` with the cwd in the scratchpad wrote into `<cwd>/sub/a.parquet` (same resolution; scratch only). Residual exposure: none in-process. Remaining caveat (not verified): a child process started with an inherited per-drive cwd environment (`=D:`) that differs from the guard's process; the stages do not spawn children for writes.

## 2. New cases against the scratch analog
| # | Case (built over the scratch analog of the protected folder) | OS oracle | Guard | Result |
|---|---|---|---|---|
| 1 | RAW mixed separators | reaches: file landed in analog | REFUSED | PASS |
| 2 | RAW doubled separators | reaches: file landed in analog | REFUSED | PASS |
| 3 | RAW doubled backslashes | reaches: file landed in analog | REFUSED | PASS |
| 4 | RAW device ns . | reaches: file landed in analog | REFUSED | PASS |
| 5 | RAW fwdslash ext //?/ | reaches: file landed in analog | REFUSED | PASS |
| 6 | RAW NT prefix ?? | reaches: file landed in analog | REFUSED | PASS |
| 7 | RAW GLOBALROOT | reaches: file landed in analog | REFUSED | PASS |
| 8 | RAW Volume{GUID} | reaches: file landed in analog | REFUSED | PASS |
| 9 | RAW UNC 127.0.0.2 C$ | no reach: open failed: OSError | EXC OSError | PASS (crash, no write) |
| 10 | RAW UNC localhost. C$ | no reach: open failed: OSError | REFUSED | PASS |
| 11 | RAW UNC ipv6-literal | reaches: file landed in analog | REFUSED | PASS |
| 12 | RAW UNC machine fqdn | reaches: file landed in analog | REFUSED | PASS |
| 13 | RAW UNC own LAN ip | reaches: file landed in analog | REFUSED | PASS |
| 14 | RAW 8.3 short name C:\Users\sikha\AppData\Local\Temp\claude\D--CYB~3\B020CB~1\SCRATC~1\pg2\an\data\raw | reaches: file landed in analog | REFUSED | PASS |
| 15 | RAW ADS ::$DATA on file | reaches: file landed in analog | REFUSED | PASS |
| 16 | RAW dir trailing dot | reaches: file landed in analog | REFUSED | PASS |
| 17 | RAW dir trailing space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 18 | RAW dir trailing dot+space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 19 | RAW dir trailing NBSP | no reach: open failed: FileNotFoundError | allowed | PASS |
| 20 | RAW dir trailing ZWSP | no reach: open failed: FileNotFoundError | allowed | PASS |
| 21 | RAW every part trailing dot | reaches: file landed in analog | REFUSED | PASS |
| 22 | RAW every part trailing space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 23 | RAW fullwidth names | no reach: open failed: FileNotFoundError | allowed | PASS |
| 24 | RAW dir:$I30:$INDEX_ALLOCATION/x | reaches: file landed in analog | REFUSED | PASS |
| 25 | RAW dir::$INDEX_ALLOCATION/x | reaches: file landed in analog | REFUSED | PASS |
| 26 | DS mixed separators | reaches: file landed in analog | REFUSED | PASS |
| 27 | DS doubled separators | reaches: file landed in analog | REFUSED | PASS |
| 28 | DS doubled backslashes | reaches: file landed in analog | REFUSED | PASS |
| 29 | DS device ns . | reaches: file landed in analog | REFUSED | PASS |
| 30 | DS fwdslash ext //?/ | reaches: file landed in analog | REFUSED | PASS |
| 31 | DS NT prefix ?? | reaches: file landed in analog | allowed | FAIL |
| 32 | DS GLOBALROOT | reaches: file landed in analog | allowed | FAIL |
| 33 | DS Volume{GUID} | reaches: file landed in analog | allowed | FAIL |
| 34 | DS UNC 127.0.0.2 C$ | no reach: open failed: OSError | EXC OSError | PASS (crash, no write) |
| 35 | DS UNC localhost. C$ | no reach: open failed: OSError | allowed | PASS |
| 36 | DS UNC ipv6-literal | reaches: file landed in analog | allowed | FAIL |
| 37 | DS UNC machine fqdn | reaches: file landed in analog | REFUSED | PASS |
| 38 | DS UNC own LAN ip | reaches: file landed in analog | allowed | FAIL |
| 39 | DS 8.3 short name C:\Users\sikha\AppData\Local\Temp\claude\D--CYB~3\B020CB~1\SCRATC~1\pg2\an\CYBER_~1 | reaches: file landed in analog | REFUSED | PASS |
| 40 | DS ADS ::$DATA on file | reaches: file landed in analog | REFUSED | PASS |
| 41 | DS dir trailing dot | reaches: file landed in analog | REFUSED | PASS |
| 42 | DS dir trailing space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 43 | DS dir trailing dot+space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 44 | DS dir trailing NBSP | no reach: open failed: FileNotFoundError | allowed | PASS |
| 45 | DS dir trailing ZWSP | no reach: open failed: FileNotFoundError | allowed | PASS |
| 46 | DS every part trailing dot | reaches: file landed in analog | REFUSED | PASS |
| 47 | DS every part trailing space | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 48 | DS fullwidth names | no reach: open failed: FileNotFoundError | allowed | PASS |
| 49 | DS dir:$I30:$INDEX_ALLOCATION/x | reaches: file landed in analog | REFUSED | PASS |
| 50 | DS dir::$INDEX_ALLOCATION/x | reaches: file landed in analog | REFUSED | PASS |
| 51 | RAW ADS :evil on folder | reaches: stream created on the analog folder | allowed | FAIL |
| 52 | DS ADS :evil on folder | reaches: stream created on the analog folder | allowed | FAIL |
| 53 | RAW junction | reaches: file landed in analog | REFUSED | PASS |
| 54 | RAW junction chain j2->j1->target | reaches: file landed in analog | REFUSED | PASS |
| 55 | RAW symlink dir | -: NOT RUN: mklink /D refused: You do not have sufficient privilege to perform this operation. | - | NOT RUN |
| 56 | RAW abs: junction then .. .. then protected | reaches: file landed in analog | REFUSED | PASS |
| 57 | RAW relative cwd=deep via junction and .. | reaches: file landed in analog | REFUSED | PASS |
| 58 | RAW relative bare name, cwd=protected | reaches: file landed in analog | REFUSED | PASS |
| 59 | RAW relative ./x, cwd=protected | reaches: file landed in analog | REFUSED | PASS |
| 60 | DS junction | reaches: file landed in analog | REFUSED | PASS |
| 61 | DS junction chain j2->j1->target | reaches: file landed in analog | REFUSED | PASS |
| 62 | DS symlink dir | -: NOT RUN: mklink /D refused: You do not have sufficient privilege to perform this operation. | - | NOT RUN |
| 63 | DS abs: junction then .. .. then protected | reaches: file landed in analog | REFUSED | PASS |
| 64 | DS relative cwd=deep via junction and .. | reaches: file landed in analog | REFUSED | PASS |
| 65 | DS relative bare name, cwd=protected | reaches: file landed in analog | REFUSED | PASS |
| 66 | DS relative ./x, cwd=protected | reaches: file landed in analog | REFUSED | PASS |
| 67 | RAW literal %CD%/data/raw | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 68 | RAW long 360 chars then .. back | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 69 | RAW 250-char dir then .. | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 70 | DS ~40k chars then .. back | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 71 | DS 5000-char component | no reach: open failed: FileNotFoundError | REFUSED | PASS |
| 72 | odd string '' | n/a: no analog; guard behaviour only | allowed | INFO |
| 73 | odd string ' ' | n/a: no analog; guard behaviour only | allowed | INFO |
| 74 | odd string '.' | n/a: no analog; guard behaviour only | allowed | INFO |
| 75 | odd string '..' | n/a: no analog; guard behaviour only | allowed | INFO |
| 76 | odd string 'x\x00y' | n/a: no analog; guard behaviour only | allowed | INFO |
| 77 | odd string 'D:' | n/a: no analog; guard behaviour only | allowed | INFO |
| 78 | odd string 'CON' | n/a: no analog; guard behaviour only | allowed | INFO |
| 79 | odd string 'NUL' | n/a: no analog; guard behaviour only | allowed | INFO |

## 3. Result summary and reproductions
79 rows: 60 PASS, 2 PASS (guard raises OSError on `\\127.0.0.2\...`, so the stage would abort before any write: safe, but a traceback), 8 INFO (odd strings), 2 NOT RUN (symlinks), 7 FAIL. Every FAIL is on the dataset folder or on an alternate data stream of a protected folder; the `data/raw` side is held by the any-`data`-`raw`-parts clause except for the stream case.

| # | FAIL (guard allows, OS reaches) | Reproduction (real constants; guard only, nothing written) |
|---|---|---|
| F-a | NT object prefix `\??\D:\Cyber_DataSet\x` | scratch analog `\??\C:\...\Cyber_DataSet\x.parquet` landed in the analog; real string `\??\D:\Cyber_DataSet\x`: `forbidden_reason` returns None (the guard strips only `//?/` and `//./` prefixes) |
| F-b | `\\?\GLOBALROOT\Device\HarddiskVolume5\Cyber_DataSet\x.parquet` | `forbidden_reason` returns None (allowed); analog with `HarddiskVolume3` for C: wrote the file |
| F-c | `\\?\Volume{fcf459af-bb60-412a-960c-6979b1cc2127}\Cyber_DataSet\x.parquet` | allowed; analog with the C: volume GUID wrote the file |
| F-d | UNC via IPv6 literal `\\0-0-0-0-0-0-0-1.ipv6-literal.net\D$\Cyber_DataSet\x` | allowed; analog on `C$` wrote the file |
| F-e | UNC via the machine's own LAN IP `\\192.168.1.7\D$\Cyber_DataSet\x` (the guard knows only `localhost`, `127.0.0.1`, `::1` and the host name) | allowed; analog on `C$` wrote the file; the guard did refuse the same path with the machine FQDN |
| F-f | Alternate data stream on the folder itself `D:/Cyber_DataSet:evil` and `D:/CyberAgents/data/raw:evil` | allowed; analog: `open("<analog>:evil","w")` created a stream on the analog directory (modifies the protected folder object, adds no file) |

The `\\localhost.\D$` (trailing dot) form is allowed but the OS refused it (OSError), so no exposure. `127.0.0.2` raises OSError inside the guard.

Severity: Low (all need deliberate crafting of a path; no normal use produces them; the dataset folder only, plus stream-on-folder). They matter because the stated purpose of the guard is that no output path can reach the source folder, and F-b to F-e are exactly the "N1 forms" the data-engineer set out to close, in four more spellings. The family is open-ended (every alias the OS accepts); string-prefix stripping cannot close it.

Recommended fix (for the data-engineer, not done by me): stop enumerating spellings. Either (1) accept only plain `X:\...` drive-letter paths (refuse any path starting with `\\` or `\??\`, or containing `:` after position 1, or a UNC), or (2) compare file identity: walk up to the nearest existing ancestor of the target and compare `os.stat` (volume serial and file index) or `os.path.samefile` with the two protected folders; this is alias-proof. Add F-a to F-f to `test_path_guard` on the scratch analog (the pattern in this file works: build the variant, write through it, assert refusal).

## 4. Real-constant strings (guard only, nothing written)
| Case | String | Guard result (real constants) |
|---|---|---|
| real GLOBALROOT D: dataset | `'\\\\?\\GLOBALROOT\\Device\\HarddiskVolume5\\Cyber_DataSet\\x.parquet'` | allowed |
| real Volume{GUID} D: dataset | `'\\\\?\\Volume{fcf459af-bb60-412a-960c-6979b1cc2127}\\Cyber_DataSet\\x.parquet'` | allowed |
| real device ns .D: dataset | `'\\\\.\\D:\\Cyber_DataSet\\x'` | REFUSED (the source dataset folder D:/Cyber_DataSet/) |
| real mixed separators dataset | `'D:/Cyber_DataSet\\x.parquet'` | REFUSED (the source dataset folder D:/Cyber_DataSet/) |
| real doubled separators dataset | `'D:\\\\Cyber_DataSet\\\\x'` | REFUSED (the source dataset folder D:/Cyber_DataSet/) |
| real short name guess dataset | `'D:/CYBERD~1/x'` | allowed |
| real ADS on dataset folder | `'D:/Cyber_DataSet:evil'` | allowed |
| real ADS file dataset | `'D:/Cyber_DataSet/x::$DATA'` | REFUSED (the source dataset folder D:/Cyber_DataSet/) |
| real raw GLOBALROOT | `'\\\\?\\GLOBALROOT\\Device\\HarddiskVolume5\\CyberAgents\\data\\raw\\x'` | REFUSED (data/raw/) |
| real ADS on raw folder | `'D:/CyberAgents/data/raw:evil'` | allowed |
| real raw trailing NBSP | `'D:/CyberAgents/data/raw\xa0/x'` | allowed |
| real fullwidth raw | `'D:/CyberAgents/ｄａｔａ/ｒａｗ/x'` | allowed |
| real %CD% | `'%CD%\\data\\raw'` | REFUSED (data/raw/) |
| real relative data/raw | `'data/raw/x'` | REFUSED (data/raw/) |
| real 8.3 CYBERA~1/data/raw | `'D:/CYBERA~1/data/raw/x'` | REFUSED (data/raw/) |

Also allowed by the real guard (measured, strings only): `\\192.168.1.7\D$\Cyber_DataSet\x`, `\\0-0-0-0-0-0-0-1.ipv6-literal.net\D$\Cyber_DataSet\x`, `\??\D:\Cyber_DataSet\x`. 8.3 short names: `GetShortPathNameW` on the real dataset folder returns the long name (8.3 generation is off on D:), so there is no short-name alias on this machine; on the analog (8.3 on) the guard refused the short form because `realpath` expands existing short names (PASS).

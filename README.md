# SchoolList

JSON fixture for CycleUni's admin School bulk-import feature.

- **Target API**: `POST /api/v1/admin/schools/bulk/` (`adminapi.views.AdminSchoolBulkImportView`, staff-only)
- **Request body**: `{"action": "preview" | "apply", "items": [...]}` — send `schools.json`'s `items` array as-is
- **Matching key**: `email_domain` (unique on the `School` model) — re-importing is idempotent; unchanged rows are skipped, differing rows are reported as `modified`
- **Field shapes**: `name` is the canonical English name, `region` is the CycleUni `Region.code`, `translations` holds localized fields keyed by language code

Contents: 101 real universities — 88 Taiwanese (`region: "TW"`, `zh-TW` names) and 13 Hong Kong (`region: "HK"`, `zh-HK` names) — with their real student-email domains. Tested end-to-end against the live endpoint in `CycleUni-BE/tests/test_bulk_import_fixtures.py`.

The build script also outputs region-specific files (`schools.TW.json`, `schools.HK.json`).
- Use `schools.json` if you are a superuser and want to import everything at once.
- Use `schools.<region>.json` if you are a regional admin managing a specific area, to avoid importing data outside your jurisdiction (which will be marked as forbidden/skipped).
## Region is required

`School.region` is non-null, and the import writes `item["region"]` straight into it. An item without a region fails the whole batch; an item with the wrong one lets students of one market verify with another market's campus domain. Every item therefore carries a region, and `4_build_schools.py` stamps it from `--region`.

Regions are also why translations are not keyed to a fixed language: Taiwan uses `zh-TW`, Hong Kong `zh-HK`. Both are Traditional Chinese but differ in vocabulary, and CycleUni serves them as separate languages.

## Pipeline

```bash
# 1. Filter the world dataset by ISO 3166-1 alpha-2 code
python3 1_filter_universities.py --country TW     # -> tw_universities.json
python3 1_filter_universities.py --country HK     # -> hk_universities.json

# 2-3. Add Chinese names (Taiwan: LLM-translated, then applied)
python3 2_translate_schools_zhTW.py
python3 3_apply_zh_name.py

# 4. Merge into the bulk-import fixture, stamping the region
python3 4_build_schools.py --input tw_universities.json --region TW
python3 4_build_schools.py --input hk_universities.json --region HK
```

Steps 2-3 are for Taiwan only. Hong Kong's Chinese names are *registered institutional
names*, not translations — 香港理工大學 is the university's actual name, and an LLM asked
to translate "The Hong Kong Polytechnic University" will happily return a plausible-but-wrong
variant like 香港理工學院. They are curated in step 1's output instead.

## Source-data caveats

The upstream `world_universities_and_domains.json` needs filtering beyond the country code,
handled in `1_filter_universities.py`:

- **Non-universities**: `cdnis.edu.hk` (Canadian International School of Hong Kong) is K-12.
  Left in, its domain would pass campus-email verification.
- **Campuses in another region**: `cuhk.edu.cn` is CUHK-Shenzhen — same name, mainland China,
  different domain. It would give one Hong Kong university a second "valid" campus domain.

It also lists some universities twice under different English spellings sharing one domain
(`nthu.edu.tw`, `nchu.edu.tw`, `nsysu.edu.tw`). Since `email_domain` is the unique key, the
duplicate would be reported as `modified` on every import and flip the stored name back and
forth. `4_build_schools.py` collapses them to the first occurrence and reports what it dropped.

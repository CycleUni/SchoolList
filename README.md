# SchoolList

JSON fixture for CycleUni's admin School bulk-import feature.

- **Target API**: `POST /api/v1/admin/schools/bulk/` (`adminapi.views.AdminSchoolBulkImportView`, staff-only)
- **Request body**: `{"action": "preview" | "apply", "items": [...]}` — send `schools.json`'s `items` array as-is
- **Matching key**: `email_domain` (unique on the `School` model) — re-importing is idempotent; unchanged rows are skipped, differing rows are reported as `modified`
- **Field shapes**: `name` is the canonical English name, `translations` holds localized fields keyed by language code (currently `zh-TW`)

Contents: 18 real Taiwanese universities with their real student-email domains. Tested end-to-end against the live endpoint in `CycleUni-BE/tests/test_bulk_import_fixtures.py`.

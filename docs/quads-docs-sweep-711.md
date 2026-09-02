# QUADS Docs Sweep Report (issue #711)

Verified: 2026-09-02 against the current `development` branch (code is ground truth).
Scope: CLI, config, API, quads-web, plugins, tools, packaging, docs/, README, swagger.yaml.

Issues filed for code/config fixes: #712 #713 #714 #715 #716 #717 #718 #719 #720.

---

## CLI (`quads --help` / parser.py / cli.py vs README)

Fixed in this sweep (README.md):
- `--schedule-stop` -> `--schedule-end` (Future Assignment Reporting)
- `--modify-notification` -> `--mod-notification`
- `--ls-retire` -> `--ls-retired`
- `--move-host` -> `--move-hosts` (prose)
- `--rm-host <host>` -> `--rm-host --host <host>` (would have exited 2)
- `--mod-schedule` example: removed doubled flag and `"22 :00"` date typo
- `--mod-interface` example: `--no-pxe-boot`-only command fails in the CLI; example now uses `--interface-speed 1000`
- `--verify-switch-conf --host + --cloud` "straddle clouds" example removed (args are mutually exclusive; the shown warning text is unreachable)
- `--ls-interfaces` -> `--ls-interface`
- `--os-list` stray leading space in prose
- `--define-cloud --boot-order director` example corrected (was attributed to `--mod-cloud`, which does not accept `--boot-order`)
- TOC: fixed "Ordering Elements in the Dynamic Wiki Content" label; added missing "Get Host Details", "Get Hosts in a Cloud", "Self-Scheduling Hosts" entries; pointed "QUADS Plugin Architecture" at the local heading
- Broken links: `/quads-api.md` -> `/docs/quads-api.md`; `jira_ticket_message` -> `jira_ticket_assignment`
- Removed phantom `summary:` plugin from the custom-plugin example
- "supybot/notify" IRC claim removed
- Fixed unclosed code fence in "Deleting Self Service Users"

Filed as issues:
- #712 `--mod-interface` pxe/maintenance-only toggles always fail (`hasattr` on a dict)
- #713 `--mod-cloud` ignores `--boot-order`
- #714 `--move-command` + `default_move_command` point at deleted `move_and_rebuild.py` and are a no-op

Undocumented real verbs/flags (noted, not necessarily needing docs): `--version`, `--ls-owner`, `--ls-cc-users`, `--ls-ticket`, `--ls-wipe`, `--ls-clouds`, `--rm-cloud`, `--ls-memory`, `--ls-disks`, `--ls-cpu`, `--ls-gpu`, `--ls-vlan`, `--ls-expirations`, `--define-host-details`, `--export-host-details`, `--metadata`, `--rm-host-metadata`, `--omit-cloud`, `--maintenance/--no-maintenance`, `--interface-bios-id`, `--blade`, `--fail/--success/--pre-initial/--pre/--one-day/--three-days/--five-days/--seven-days`.

## Config (`conf/*.yml` vs conf_check.py vs docs)

Fixed in this sweep:
- README: `lab_name` anchor moved from `quads.yml` to `quadsweb.yml`; `models:` anchor corrected to `quads.yml`
- `docs/quads-host-metadata-search.md`: `models:` now referenced in `quads.yml`, not `hosts_metadata.yml`
- `docs/switch-host-setup.md`: IPMI credentials anchor corrected to `quads.yml`; `INTERFACES` anchor corrected to `config.py`
- README notifications section now notes email/chat delivery config lives in `plugins.yml` (content keys stay in `quads.yml`)

Verified accurate: README "Verifying Configuration" table matches `conf_check.py` exactly; `quads --conf-check` wiring correct.

Filed as issues:
- #719 dead/broken config keys: `default_wipe` (quads.yml), `ssm_enable_sched_window` (selfservice.yml), `plugins.aws_cloud` (plugin name is `aws`), `plugins.foreman.default_ptable`/`default_medium` (never read)
- #720 cron header omits `--notify`; dead `quads-regen-heatmap.log` logrotate rule

Note: `${VAR}` placeholders in `plugins.yml` are literal strings (no env substitution); README/docs now state this.

## API (`src/quads/server/blueprints/*` vs swagger.yaml vs docs/quads-api.md)

Fixed in this sweep:
- swagger.yaml: removed non-resolving internal server hostnames (kept example host)
- Added 14 missing endpoints: `GET /assignments/expirations/`, `GET /assignments/{id}/ssh-keys`, `GET /hosts/availability_summary`, `GET /schedules/stats/build_delta`, `GET /schedules/stats/utilization`, `POST /schedules/batch`, `GET/POST|PATCH /moves/progress/*`, `GET/POST /users/`, `GET/PATCH /users/{email}`
- Corrected request bodies to match code: `POST /clouds/` (`cloud` not `name`), `POST /hosts/` (required name/model/host_type/rack/uloc, `default_cloud` name), `POST /assignments/` (required description/owner/ticket/cloud), `POST /assignments/self/` (`cc_user`, no `owner`), `POST /disks//PATCH` (`disk_id`), `POST /interfaces/PATCH` (`id`), `POST /memory/`, `POST /processors/`, `POST /schedules/` (hostname/cloud), `POST /vlans/`
- Response codes aligned to code: create/PATCH endpoints that return HTTP 200 documented as 200
- Added `MoveProgress` schema; `GET /schedules/` and `GET /assignments/` documented as arrays
- `docs/quads-api.md`: corrected the "all GET requests require no auth" claim; expanded GET/POST/PATCH endpoint lists; fixed `POST /interfaces` to `POST /interfaces/{hostname}`; removed ignored `active`/`provisioned`/`validated` keys from the assignment example and `assignment_id` from the schedule example

Filed as issues:
- #716 API HTTP status codes (login body `201` vs HTTP `200`; create endpoints return `200` not `201`)

Verified: every swagger path now resolves to a live blueprint route; every `quads_api.py` client endpoint exists server-side.

## quads-web (`src/quads/web/*` vs docs vs templates)

Fixed in this sweep:
- `docs/quads-self-schedule.md`: login token extraction (`awk` -> `jq -r .auth_token`), `owner` payload field removed (derived from token), `ticket` required unless `ssm_jira_create_ticket` enabled, "disabled by default" claim corrected (shipped `ssm_enable: true`), end-date phrasing (deadline window may override lifetime)
- `docs/google-oauth-setup.md`: local redirect port `5000` -> `5001`; ID token -> userinfo wording
- README dynamic-content excludes noted as `.git static instack visual`, not just `static`

Verified accurate: API Tokens section, self-scheduled report, available web UI, all `/auth/*` routes, wiki/dynamic content.

Filed as issues:
- #715 `/results` and `/available_hosts` routes are unreachable (missing URL converter); dead templates `_formhelpers.html`, `dropdown.html`, `links.html`

## Plugins (`quads-plugins.md`, `using-jira-with-quads.md`, plugins.yml)

Fixed in this sweep:
- `docs/using-jira-with-quads.md`: rewritten for `plugins.jira` config in `plugins.yml` (`auth_type`/`url`/`username`/`password`/`token`/`ticket_queue`); removed dead top-level `jira_url`/`jira_auth`/`jira_username`/`jira_password`/`jira_token` keys; corrected library path to `src/quads/tools/external/jira.py`; corrected `jira_watchers.py` path; added `jira_workflow.py`
- `docs/quads-plugins.md`: added Cloud and Dayzero plugin categories; corrected interface methods (email `send_mail`, hardware `init/set_power_state/reboot_server/get_power_state/get_vendor`, provisioner `prepare_host_provisioning/get_all_hosts/get_images`, release `move_and_rebuild`, switch `configure/modify/verify/ls_config`, ticketing `create_ticket/post_comment/get_ticket/get_transitions/post_transition`); removed `aws_cloud` block (broken config key) and `max_instances`; removed `irc ssl/nickname` (never read); removed `foreman.default_ptable/default_medium`; added `skip_for_supermicro_models`, `mail_display_name`, `rbac_user_mail`, `rbac_auth_source_id`, `ipmi_credential_retries/retry_delay`; removed false `${VAR}` env-substitution claim; added `dayzero` to discovery paths; fixed custom plugin location list; fixed code migration example

Filed as issues:
- #719 (config key mismatch `aws_cloud` vs `aws`, dead `default_ptable/default_medium`)

## Tools / cron / packaging

Verified: all 6 cron entries map to real CLI flags; switch/tool CLI flags all exist.

Filed as issues:
- #714 `move_and_rebuild.py` / `--move-command`
- #717 `setup.cfg` ships only 11 of 14 migrations; orphaned migration bytecode
- #718 `quads-web.service` missing DB URI env; stale `.env.example`
- #720 cron header / logrotate

Docs fixed in this sweep:
- `docs/quads-workflow.md`: `move_and_rebuild.py` caption replaced (plugin workflow); TOC anchor fixed; added missing "Workload Assignments Readiness" TOC entry; supybot + "7 days prior" wording corrected
- `docs/quads-schema-change.md`: `systemctl status postgresql` -> `quads-db`; "complete drop of all tables" claim corrected; "udner" typo
- `docs/quads-scale-limits.md`: "Theoritical" -> "Theoretical" (heading + TOC anchor); "multi-Forman" -> "multi-Foreman"
- `docs/switch-host-setup.md`: removed stale "moving to libssh" note; corrected two line anchors
- `docs/quads-host-metadata-search.md`: `--export-host-details` usage corrected; `disks.disks_type` -> `disks.disk_type`; `interfaces__size=` -> `interfaces.count`; `--ls-host` -> `--ls-hosts` (x2); `models:` link fixed; re-import semantics corrected; "Querying Host Status" future-tense fixed
- README move-host section rewritten for the plugin-based workflow; `--move-command` external-script model removed

## Remaining risk / follow-up

- Web `/results` and `/available_hosts` (issue #715), CLI pxe/maintenance toggles (#712), mod-cloud boot-order (#713) are code gaps; the docs no longer claim these work.

# Work Roots For This Release

- **Reviewed development copy:** `/home/lijunjie/grok-register-panel-hardening-ui`
- **Live self-use runtime:** `/data/compose/grok-register-camoufox`
- **Synchronized hardening copy:** `/data/compose/grok-register-panel-hardening`
- **Rollback snapshot:** `/data/backups/grok-register-release-20260730T044241Z`

Before cutover, migrate the legacy blacklist and verify no registration or
recovery process is active. Synchronize code while excluding runtime state,
then restart only the panel service and run the release checklist.

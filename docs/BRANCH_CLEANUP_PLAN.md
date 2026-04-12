# zoho-cleanup-working branch

This branch is the safe working copy of `main` for turning `uk_pm_monitoring` into a cleaner production backend without disturbing the current running setup.

## Goal
Create one stable backend that can later absorb the best parts of `pm-monitoring-dashboard` and serve as the common data/API layer for the SGN website.

## Changes already started
1. Added SQL migration for missing extended telemetry columns:
   - `lux`
   - `uv_index`
   - `battery_percent`
2. Added `.env.zoho.example` for deployment bootstrap.

## Next cleanup items
1. Fix `process_sensor_data()` undefined variable usage.
2. Fix MQTT client key mismatch between `device_id` and `data_source_id`.
3. Remove demo auth bypasses from dashboard/API routes.
4. Remove Railway-specific startup assumptions and replace with cleaner production startup flow.
5. Split large `app.py` into smaller modules.
6. Add deployment notes for Zoho and AWS.
7. Freeze common API contract for SGN website integration.

## Immediate production concern
Current `app.py` reads/writes fields that are not fully represented in the base schema. Run migrations before fresh deployment.

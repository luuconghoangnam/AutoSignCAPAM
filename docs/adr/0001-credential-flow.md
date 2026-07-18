# ADR-0001: Credential Flow

Status: Accepted
Date: 2026-07-18
Commit: pending

## Context

Automation signs in to GlobalProtect, CAPAM, and Windows Security. OTP rotates every 30 seconds, so each run requires fresh interactive input. Credentials must not be persisted in settings, logs, screenshots, or diagnostic JSON.

## Constraints

- User supplies a fresh six-digit OTP immediately before starting each run.
- UI clears OTP when a run finishes.
- Password prefix and OTP are not saved to the settings file.
- Each credential transaction submits once and then waits for a classified postcondition.

## Decision

| State | Username | Password composition |
|---|---|---|
| GlobalProtect Credentials | configured username | `password_prefix + otp` |
| CAPAM Login | configured username | `password_prefix + otp` |
| Windows Security | configured username | `password_prefix` |

The existing UI is the input boundary. User enters password prefix and a current OTP, selects target device, then presses Enter or clicks `TIEN HANH DANG NHAP`. Automation must not request or accept OTP through logs, command-line arguments, environment variables, or diagnostic files.

Login-only success requires a verified authenticated CAPAM state. Sending credentials alone is not success.

## Consequences

- Runs delayed beyond the OTP validity window may return authentication failure and must not resubmit automatically.
- A new run requires a new OTP.
- Full-flow testing requires the user present at run start, but not during later guarded actions unless a failure occurs.

## Rollback

Cancel before submission or disable automation. Never change password composition as a runtime fallback after authentication failure.

## Follow-up Gates

- Record baseline outcomes by FSM state without credential values.
- Verify auth failure classification with an expired OTP in a controlled test.
- Verify no diagnostic artifact contains password prefix or OTP.

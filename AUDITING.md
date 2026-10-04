# Auditing Bitcoin Core Feature Overlay

This is review guidance, not a completed audit. Record evidence and findings for each actual utility in [AUDIT.md](AUDIT.md). Copying the scaffold does not transfer review coverage.

## Establish the review target

Record the canonical scaffold commit, downstream project commit, generator and launcher blob hashes, Core release and source commit, archive hash, OS version and other dependencies. Identify the missing upstream feature and the Core RPC contracts it relies on. Review the exact files that will execute, including local changes.

## Review the three layers together

1. **Generator:** check RPC inputs, wallet selection, key/descriptor paths, handling of secrets, errors and verified postconditions. Confirm that Bitcoin primitives stay in Core and OS enforcement stays in the launcher. Check that sensitive RPC values do not enter process arguments or logs.
2. **Launcher:** check dependency availability, authenticated acquisition and archive pin verification, extraction and absolute binary paths, version enforcement, network/isolation assumptions, fresh state, output collisions, startup, shutdown and cleanup on success, failure and interruption. The Tails example stops existing Core processes; review that impact explicitly. Do not assume process-level network flags establish a physical air gap.
3. **Human/audit documents:** check that preparation, software verification, backup, recovery, storage and end-to-end testing match executable behavior. Describe every private/public artifact and any state or extracted files left behind. State limitations and distinguish verified results from planned tests.

## Exercise failures and recovery

Test placeholders failing closed; missing dependencies; missing, corrupt or wrong-version Core archives; existing outputs; RPC errors; interruption and cleanup. Test the complete feature and independent backup recovery in its intended OS/Core environment, using regtest or disposable funds where applicable. Record commands or procedures, expected outcomes and observed results. Passing syntax checks alone is not an end-to-end test or an audit.

## Maintain review evidence

List scope, reviewer, date, findings, fixes, unresolved risks and exact tested revisions in `AUDIT.md`. Re-review generator changes and test every Core pin change. Review launcher and procedure changes against the preserved generator contract. Never label an inherited baseline as reviewed without evidence.

When equivalent functionality lands in Core, assess behavior and backup compatibility before retiring the overlay. Document the migration and verification procedure rather than automatically replacing an existing user's workflow.

# Settled Protocol — HookV1 Agent Execution Firewall

**Status:** Experimental research prototype  
**Language:** Vyper `0.4.3`, Solidity test harness, Python / Ape  
**Standard target:** ERC-7579 Hook module (module type `4`)  
**Testing status:** 7 HookV1 integration tests passing in the recorded baseline

---

## 1. Overview

HookV1 is an experimental on-chain execution firewall for smart accounts executing actions on behalf of autonomous AI agents.

The objective is to enforce execution policy at the smart-account boundary rather than relying exclusively on the agent's reasoning, prompts, or application-level restrictions.

An agent may propose and sign an operation using an authorized session key, but the smart account's execution path should enforce the applicable restrictions before the operation proceeds.

HookV1 explores the following controls:

- Target-address allowlisting.
- Function-selector blocking.
- Rejection of unsupported execution modes.
- ERC-20 spending limits based on pre-execution and post-execution balance snapshots.
- Cumulative spending caps.
- Emergency pause controls.
- Owner-authorized policy changes.
- Atomic transaction rollback when execution violates an enforced limit.

**Research question:** Can an execution hook constrain the financial effects of autonomous agent operations at the smart-account execution layer, independently of whether the agent's decision-making process is trustworthy?

This implementation is an experimental prototype. Passing tests demonstrate the tested behavior under the test harness; they do not establish complete ERC-7579 compatibility or production security.

## 2. Architecture

The current test environment consists of three principal components.

### HookV1.vy

The firewall contract. It maintains per-account configuration, checks execution calldata, validates the target and function selector, snapshots the tracked ERC-20 balance, and enforces spending limits after execution.

### Mock7579Account.sol

A simplified smart-account test harness that invokes the hook's `preCheck` and `postCheck` around a target call.

It allows integration tests to exercise the hook's intended execution sequence without requiring a production smart-account implementation.

The mock is not, by itself, evidence of full ERC-7579 compliance.

### MockUSDC.vy

A mock ERC-20 token used to test balance changes and spending limits. Despite its name, the provided implementation uses 18 decimals, so its values should not be interpreted as production USDC units.

### Execution flow

1. The smart account invokes `preCheck`.
2. The hook verifies installation and pause status.
3. The hook validates the execution mode and target.
4. The hook rejects blocked function selectors and the tested direct `transferFrom` drain pattern.
5. The hook snapshots the tracked token balance.
6. The smart account executes the target call.
7. The hook's `postCheck` measures the resulting token balance.
8. If the measured spend exceeds either configured limit, the transaction reverts.
9. Otherwise, the hook records the spend in its cumulative accounting.

Because `postCheck` executes within the transaction in this harness, a failed spending-limit check reverts the transaction's state changes atomically.

## 3. Enforcement mechanisms

### 3.1 Target allowlisting

Each account has its own target allowlist.

The hook rejects execution when the decoded target is not whitelisted for the calling smart account.

Initial whitelist entries are supplied during installation. The configured owner can subsequently update the allowlist.

### 3.2 Function-selector restrictions

The hook blocks these function selectors:

| Function | Selector |
|---|---|
| `approve(address,uint256)` | `0x095ea7b3` |
| `increaseAllowance(address,uint256)` | `0x39509351` |
| `permit(address,address,uint256,uint256,uint8,bytes32,bytes32)` | `0xd505accf` |
| `setApprovalForAll(address,bool)` | `0xa22cb465` |

The hook separately checks `transferFrom(address,address,uint256)` and rejects it when the decoded `from` address matches the smart account.

This is a targeted drain check, not a blanket prohibition on every `transferFrom` call.

### 3.3 Execution-mode restriction

HookV1 permits the single-call execution mode (`0x00`) and rejects other call types in the execution calldata.

This is intended to prevent batch and delegatecall execution paths from bypassing the V1 policy.

The guarantee depends on the correctness of the calldata parser and the smart account's actual execution format. Those assumptions require further validation against a real ERC-7579 account.

### 3.4 Per-transaction ERC-20 spending limit

The hook snapshots the configured token's balance before execution.

After execution, it calculates the net reduction:

`spent = balanceBefore - balanceAfter`

If the reduction exceeds `maxSpendPerTx`, the hook reverts.

### 3.5 Cumulative spending cap

The hook maintains `spentTotal` for each account.

The next measured spend is permitted only if:

`spentTotal + spent <= maxSpendTotal`

A successful operation increments the cumulative counter. A rejected operation must not leave behind partial accounting or token transfers.

The current implementation tracks measured ERC-20 balance reductions, not the economic value or risk of every possible action.

### 3.6 Emergency pause

The configured owner can toggle the account's pause state.

While paused, `preCheck` rejects execution.

### 3.7 Owner-authorized policy changes

The configured owner is required to authorize:

- Pause-state changes.
- Whitelist updates.
- Spending-limit updates.

Updated limits must satisfy the configured constraints, including a positive per-transaction limit, a per-transaction limit no greater than the cumulative cap, and a cumulative cap no lower than already-recorded spending.

The correctness of the configured owner depends on the installation path supplying the actual authorized owner.

## 4. Contract configuration

The per-account configuration contains:

| Field | Purpose |
|---|---|
| `initialized` | Indicates whether the firewall has been installed |
| `paused` | Indicates whether execution is paused |
| `owner` | Address authorized to update firewall policy |
| `trackedToken` | ERC-20 token whose balance changes are measured |
| `maxSpendPerTx` | Maximum measured token spend per transaction |
| `maxSpendTotal` | Maximum cumulative measured token spend |
| `spentTotal` | Recorded cumulative spend |

Installation data is ABI-encoded as:

`(owner, trackedToken, maxSpendPerTx, maxSpendTotal, initialWhitelist[4])`

The contract rejects repeated initialization, a zero owner, and invalid spending limits.

The current installation process assumes the calling smart account is authorized to install the hook and that the supplied owner is correct. Those assumptions must be verified against the real account implementation.

## 5. Test environment

The recorded development environment is:

- Python 3.11.
- Ape 0.8.50.
- pytest 8.4.2.
- Vyper 0.4.3 for HookV1.
- A local virtual environment named `.venv`.
- A local development environment under `~/settled/backend`.

The primary integration suite is:

`tests/test_hookv1_integration.py`

The separate ACEGuard regression suite is:

`tests/test_aceguard_regression.py`

ACEGuard is a separate component of the broader Settled execution-security work. Its tests should be reported separately from HookV1 results.

## 6. Integration test results

The recorded HookV1 integration run passed all seven tests.

| Test | Expected behavior | Recorded result |
|---|---|---|
| Installation records mock account | Configuration is initialized for the smart account | PASS |
| Allowed transfer records spend | Permitted transfer succeeds and measured spend is recorded | PASS |
| Non-whitelisted target reverts | Unapproved target execution is rejected | PASS |
| Approval selector is blocked | Direct blocked approval call is rejected | PASS |
| Per-transaction spending limit | An over-limit transfer reverts atomically | PASS |
| Cumulative spending limit | Total spending above the configured cap is rejected | PASS |
| Native value is not included in accounting | Confirms the current implementation's native-value accounting gap | PASS |

The final test is a limitation test. It passes because it verifies that native-value spending is not currently included in the ERC-20 balance-delta accounting. It must not be interpreted as proof of native-currency protection.

### Recorded test command

```bash
ape test tests/test_hookv1_integration.py -v
```

Recorded output:

```text
7 passed in 2.34s
```

This result applies to the code and environment used in that run. Tests should be rerun after subsequent changes.

## 7. Known limitations and unresolved security questions

### Native-currency spending

The hook accepts `msgValue` in `preCheck`, but does not enforce a native-value spending limit. `postCheck` measures only the configured ERC-20 token.

Native-currency transfers are therefore outside the current spending-limit guarantee.

**Required work:** Define native-currency per-transaction and cumulative limits, implement enforcement, and add tests for allowed transfers, rejected transfers, and atomic rollback. Native currency and ERC-20 units must be accounted for separately.

### Net balance-delta accounting

The hook measures the net balance reduction between two snapshots.

A target that can move tokens out of the account and replenish the balance during the same transaction could potentially make net loss understate outgoing transfers.

**Required work:** Build controlled adversarial fixtures and determine which balance-restoration scenarios are reachable. Evaluate whether stronger accounting or stricter execution restrictions are necessary.

### Installation and uninstallation authorization

The hook accepts an owner address from installation data. Its `onUninstall` function resets the configuration when called by the smart account.

The hook does not independently verify that the configured owner is the account's actual owner, nor does it independently require the owner to approve uninstallation.

**Required work:** Verify the real account's installation, uninstallation, and module-management authorization paths.

### Real ERC-7579 compatibility

The current mock constructs execution calldata and calls the hook around a target invocation.

That is useful for testing, but it does not prove that a production ERC-7579 account will supply the exact calldata layout, invoke the hook with the expected caller context, or enforce installation and uninstallation permissions correctly.

**Required work:** Integrate with a real ERC-7579-compatible account and run the same security tests against it.

### Other unresolved areas

- Adversarial tests for pause and policy-update authorization.
- Rejection of malformed execution calldata.
- Batch and delegatecall rejection under the actual account execution format.
- Broader `transferFrom` and allowance-related attack scenarios.
- The effects of unusual or malicious ERC-20 token behavior.
- Whether every intended execution path necessarily passes through the hook.
- Whether an agent can bypass or remove the hook through account-level functionality.

## 8. Research methodology

The project should evaluate explicit security properties rather than rely on a count of passing tests.

For each property, record:

1. **Property:** What must remain true?
2. **Threat model:** What can the agent, session key, target, or external caller control?
3. **Attack attempt:** What action attempts to violate the property?
4. **Expected result:** Revert, successful execution, or another defined outcome.
5. **Observed result:** Actual execution and state changes.
6. **Evidence:** Test case, logs, balances, counters, and transaction outcome.
7. **Limitations:** Which assumptions or untested execution paths remain?

The initial evaluation focuses on target restrictions, selector restrictions, ERC-20 spending caps, cumulative accounting, and transaction atomicity.

Future evaluation should distinguish between properties demonstrated by the mock, properties demonstrated against a real account, and properties that remain hypotheses.

## 9. Reproduction commands

Run the following from the backend project directory:

```bash
cd ~/settled/backend

ape compile

ape test tests/test_hookv1_integration.py -v

ape test tests/test_aceguard_regression.py -v

ape test -v
```

The final command runs the full test suite.

Preserve the output of each run, particularly any failure traces, and rerun the suite after modifying contract code, calldata parsing, account integration, or test fixtures.

## 10. Next milestones

### Milestone 1 — Preserve and verify the baseline

- Preserve the seven existing integration tests.
- Run the full regression suite.
- Review repository contents and ensure local secrets and generated build artifacts are not included in published commits.
- Record the exact source revision and test output.

### Milestone 2 — Adversarial HookV1 tests

Add tests for:

- Non-owner attempts to pause or unpause.
- Non-owner whitelist and spending-limit changes.
- Execution while paused.
- `transferFrom` drain attempts.
- Malformed execution calldata.
- Batch and delegatecall rejection.
- Native-currency outflows.
- Balance-delta evasion.
- Hook installation and uninstallation authorization.

### Milestone 3 — Strengthen enforcement

Implement the controls required by the findings, beginning with native-currency policy and any demonstrated balance-delta weaknesses.

Do not claim protection until the implementation and adversarial tests support that claim.

### Milestone 4 — Real account integration

Test the hook against a real ERC-7579-compatible account. Verify the hook lifecycle, caller context, calldata layout, execution modes, and account-level permissions.

### Milestone 5 — Research paper

Develop a reproducible report containing:

- Research question and motivation.
- Threat model and trust assumptions.
- System architecture.
- Security properties.
- Test methodology and attack cases.
- Results and supporting evidence.
- Limitations and unresolved risks.
- Comparison between intended policy and observed enforcement.
- Reproduction instructions.

The paper should distinguish verified behavior from assumptions and proposed future work.

## 11. Scope and disclaimer

HookV1 is a research prototype for execution-layer controls in autonomous-agent systems. It is not audited production security software.

The current evidence establishes a limited set of behaviors in a mock integration environment. It does not establish complete protection against arbitrary malicious targets, malicious tokens, compromised account administration, every execution mode, or all ways an agent might cause financial loss.

The central research objective is to determine which actions can be constrained at the execution boundary, which restrictions can be bypassed under realistic adversarial conditions, and which assumptions are required for the controls to remain effective.

---

**Project:** Settled Protocol  
**Component:** HookV1 Agent Execution Firewall  
**Current milestone:** Integration baseline established; adversarial validation and real-account compatibility remain outstanding.

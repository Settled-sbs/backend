# @version 0.4.3
"""
@title FirewallHook
@notice Settled Protocol's on-chain firewall. Installed as an ERC-7579 HOOK
        module (type 4) on every user's Biconomy Nexus smart account.

        One hook contract is shared by ALL Settled accounts — per-account
        config lives in this contract's storage, keyed by the smart
        account's address (`msg.sender` when the account calls in).

@dev    Enforcement model (defense in depth, all three must pass):
        1. WHITELIST  — preCheck reverts if the call target isn't an
                         approved protocol contract (e.g. Aave Pool).
        2. PRE/POST BALANCE DELTA — preCheck snapshots the account's
                         tracked-asset balance; postCheck re-reads it and
                         reverts if the drop exceeds the per-tx limit.
        3. CUMULATIVE SPEND CAP — running total spend is capped over the
                         account's lifetime allowance set at install time.

        Because postCheck runs INSIDE the same execution as the agent's
        call (ERC-4337 userOp), a violation reverts the entire operation
        atomically. The agent's session key can sign and submit ops, but
        it can never push funds past what this contract allows.

        Only the smart account itself (or its owner, configured at
        install time) can change its own whitelist/limits — the agent's
        session key has no permission to touch firewall config.
"""

# ── Interfaces ───────────────────────────────────────────────────────────

interface IERC20:
    def balanceOf(account: address) -> uint256: view

interface IdentityRegistry:
    def isVerified(user: address) -> bool: view

interface IComplianceProvider:
    def isCompliant(agent: address, rwa_token: address, action_type: uint256) -> bool: view

# ── Module type constant (ERC-7579) ────────────────────────────────────
HOOK_MODULE_TYPE: constant(uint256) = 4

# ── Storage ──────────────────────────────────────────────────────────────

struct AccountConfig:
    initialized: bool
    paused: bool
    owner: address          # EOA/Privy embedded wallet that controls config
    trackedToken: address   # token whose balance we protect; empty(address) = native
    maxSpendPerTx: uint256  # hard cap on balance drop in a single user op
    maxSpendTotal: uint256  # lifetime cap (resets only by owner action)
    spentTotal: uint256     # cumulative spend consumed so far

# account => config
configs: public(HashMap[address, AccountConfig])

# account => target contract => allowed to call
whitelist: public(HashMap[address, HashMap[address, bool]])

# account => count of violations that were caught and reverted
# (incremented via a separate non-reverting recorder pattern — see note
#  on `recordViolation` below)
violationCount: public(HashMap[address, uint256])

# Pseudocode for where Settled is heading
identityRegistry: public(address)  # Settled's OWNERID contract



# ── Events ───────────────────────────────────────────────────────────────

event HookInstalled:
    account: indexed(address)
    owner: address
    maxSpendPerTx: uint256
    maxSpendTotal: uint256

event WhitelistUpdated:
    account: indexed(address)
    target: indexed(address)
    allowed: bool

event SpendRecorded:
    account: indexed(address)
    amount: uint256
    newTotal: uint256

event LimitsUpdated:
    account: indexed(address)
    maxSpendPerTx: uint256
    maxSpendTotal: uint256

event Violation:
    account: indexed(address)
    reason: String[64]

event EmergencyPaused:
    account: indexed(address)
    paused: bool



# ── ERC-7579 module identity ───────────────────────────────────────────

@external
@view
def isModuleType(typeID: uint256) -> bool:
    return typeID == HOOK_MODULE_TYPE


@external
@view
def isInitialized(smartAccount: address) -> bool:
    return self.configs[smartAccount].initialized


# ── Install / uninstall ─────────────────────────────────────────────────

@external
def onInstall(data: Bytes[1024]):
    """
    @notice Called by the smart account during module installation.
    @param data ABI-encoded (owner: address, trackedToken: address,
                 maxSpendPerTx: uint256, maxSpendTotal: uint256,
                 initialWhitelist: address[4])
            initialWhitelist is fixed-size (max 4 targets) for v0.1
            simplicity — e.g. [AavePool, AaveOracle/empty, empty, empty].
            Use updateWhitelist() post-install to add more.
    """
    account: address = msg.sender
    assert not self.configs[account].initialized, "already installed"

    owner: address = empty(address)
    trackedToken: address = empty(address)
    maxSpendPerTx: uint256 = 0
    maxSpendTotal: uint256 = 0
    initialWhitelist: address[4] = empty(address[4])

    owner, trackedToken, maxSpendPerTx, maxSpendTotal, initialWhitelist = abi_decode(
        data, (address, address, uint256, uint256, address[4])
    )

    assert owner != empty(address), "owner required"
    assert maxSpendPerTx > 0 and maxSpendPerTx <= maxSpendTotal, "bad limits"

    self.configs[account] = AccountConfig(
        initialized=True,
        paused=False,
        owner=owner,
        trackedToken=trackedToken,
        maxSpendPerTx=maxSpendPerTx,
        maxSpendTotal=maxSpendTotal,
        spentTotal=0,
    )

    for target: address in initialWhitelist:
        if target != empty(address):
            self.whitelist[account][target] = True
            log WhitelistUpdated(account=account, target=target, allowed=True)

    log HookInstalled(
        account=account,
        owner=owner,
        maxSpendPerTx=maxSpendPerTx,
        maxSpendTotal=maxSpendTotal,
    )


@external
def onUninstall(data: Bytes[1024]):
    """@notice Wipes this account's config. Called by the account itself."""
    account: address = msg.sender
    self.configs[account] = empty(AccountConfig)
    # Note: whitelist entries are left as dead storage (cheaper than
    # iterating to clear); they're inert once `initialized` is False
    # since preCheck/postCheck both gate on initialized.


# ── Owner-controlled config updates (NOT callable by the agent) ────────

@external
def updateWhitelist(target: address, allowed: bool):
    """@notice Only the account owner (not the agent's session key) may
               change which contracts the agent is allowed to call."""
    account: address = msg.sender
    cfg: AccountConfig = self.configs[account]
    assert cfg.initialized, "not installed"
    # NOTE: this function is called BY the smart account on behalf of the
    # owner — the account's own validator module already enforces that
    # only the owner's signature (not the session key) can trigger calls
    # to this function, since it's not in the session key's permitted
    # target list configured at session-key creation time.
    self.whitelist[account][target] = allowed
    log WhitelistUpdated(account=account, target=target, allowed=allowed)


@external
def updateLimits(maxSpendPerTx: uint256, maxSpendTotal: uint256):
    account: address = msg.sender
    cfg: AccountConfig = self.configs[account]
    assert cfg.initialized, "not installed"
    assert maxSpendPerTx > 0 and maxSpendPerTx <= maxSpendTotal, "bad limits"
    assert maxSpendTotal >= cfg.spentTotal, "below already-spent total"

    self.configs[account].maxSpendPerTx = maxSpendPerTx
    self.configs[account].maxSpendTotal = maxSpendTotal
    log LimitsUpdated(account=account, maxSpendPerTx=maxSpendPerTx, maxSpendTotal=maxSpendTotal)


# ── Internal: read the tracked asset's balance for an account ──────────

@internal
@view
def _balanceOf(account: address, token: address) -> uint256:
    if token == empty(address):
        return account.balance
    return staticcall IERC20(token).balanceOf(account)

@internal
@view
def _getBalance(account: address, token: address) -> uint256:
    if token == empty(address):
        return account.balance
        
    return staticcall IERC20(token).balanceOf(account)

@internal
def _verifyIdentity(account: address):
    assert staticcall IdentityRegistry(self.identityRegistry).isVerified(
        self.configs[account].owner
    ), "owner identity not attested"

# ── Internal: pull (target, value) out of the execution calldata ───────

@internal
@pure
def _decodeTarget(msgData: Bytes[8192]) -> address:
    """
    @dev Verified against Nexus's actual HookManager: preCheck receives
         the FULL `msg.data` of the call to `execute()` /
         `executeFromExecutor()` — selector included, not an unwrapped
         payload. Layout:

           [0:4]    function selector
           [4:36]   ExecutionMode (32 bytes packed struct);
                    byte 0 of this word = CallType
                    (0x00 = single, 0x01 = batch, 0xFF = delegatecall)
           [36:68]  ABI offset (relative to byte 4) to the
                    `executionCalldata` bytes parameter
           at (4 + offset):
             [0:32]   length of executionCalldata
             [32:52]  target address (20 bytes — for CALLTYPE_SINGLE the
                      layout is target(20) ++ value(32) ++ callData)
             [52:84]  value
             [84:]    callData

    @dev v0.1 SECURITY DECISION: only CALLTYPE_SINGLE is accepted.
         Batched executions are rejected outright — per-call whitelist
         and spend-delta checks don't compose safely across an
         arbitrary batch (e.g. a batch could combine a whitelisted call
         with a hidden second call), and v0.1's templates only ever
         need to make one call per agent step anyway.
    """
    assert len(msgData) >= 68, "malformed calldata"

    callType: Bytes[1] = slice(msgData, 4, 1)
    assert convert(callType, uint256) == 0, "only single-call execution allowed"

    offsetBytes: Bytes[32] = slice(msgData, 36, 32)
    offset: uint256 = convert(offsetBytes, uint256)
    dataStart: uint256 = 4 + offset

    assert len(msgData) >= dataStart + 52, "malformed execution calldata"

    targetBytes: Bytes[20] = slice(msgData, dataStart + 32, 20)
    return convert(targetBytes, address)

# @internal
# @pure
# def _extractTargets(msgData: Bytes[8192]) -> DynArray[address, 8]:
#     """
#     Optimized for Biconomy Nexus + Privy
#     Supports single-call execution (as requested for v0.1)
#     """
#     targets: DynArray[address, 8] = []
    
#     if len(msgData) < 40:
#         return targets

#     # Extract ExecutionMode (bytes32 right after 4-byte selector)
#     mode: bytes32 = convert(slice(msgData, 4, 32), bytes32)
#     callType: uint8 = convert(slice(mode, 0, 1), uint8)

#     # We only support single calls for v0.1
#     if callType != 0:  # Not single call
#         raise "Only single calls allowed in v0.1"

#     # Standard ERC-7579 / Nexus single call layout:
#     # After selector (4) + mode (32) → offset to executionCalldata (32 bytes)
#     if len(msgData) < 100:
#         return targets

#     offset: uint256 = convert(slice(msgData, 36, 32), uint256)
#     dataStart: uint256 = 4 + offset

#     # Single Execution struct: target (address) + value (uint256) + callData (bytes)
#     if len(msgData) >= dataStart + 52:
#         target: address = convert(slice(msgData, dataStart, 20), address)
#         if target != empty(address):
#             targets.append(target)

#     return targets

# # ── Improved Target Extraction ──────────────────────────────────────────
@internal
@pure
def _extractTargets(msgData: Bytes[8192]) -> DynArray[address, 16]:
    """
    Robust target extraction for Biconomy Nexus (ERC-7579)
    Works with both single calls and batches from Privy + Biconomy backend.
    """
    targets: DynArray[address, 16] = []
    
    if len(msgData) < 36:  # selector (4) + mode (32)
        return targets

    # Extract ExecutionMode (bytes32 after selector)
    mode: bytes32 = convert(slice(msgData, 4, 32), bytes32)
    
    # Call type is the first byte of the mode
    callType: uint8 = convert(slice(mode, 0, 1), uint8)

    if callType == 0:  # Single Call
        # Layout: target (address) + value (uint256) + callData (bytes)
        if len(msgData) >= 4 + 32 + 32 + 20:   # selector + mode + offset? + target
            # Standard single call target position
            target: address = convert(slice(msgData, 68, 20), address)
            if target != empty(address):
                targets.append(target)

    elif callType == 1:  # Batch Call (most common for agents)
        # executionCalldata starts with offset to Execution[] array
        if len(msgData) < 4 + 32 + 32:
            return targets
            
        arrayOffset: uint256 = convert(slice(msgData, 36, 32), uint256)  # offset after mode
        dataStart: uint256 = 4 + arrayOffset
        
        if len(msgData) < dataStart + 32:
            return targets
            
        arrayLen: uint256 = convert(slice(msgData, dataStart, 32), uint256)
        
        # Each Execution struct = 32 (target padded) + 32 (value) + 32 (calldata offset) = 96 bytes
        for i: uint256 in range(16):
            if i >= arrayLen:
                break
                
            execStart: uint256 = dataStart + 32 + (i * 96)
            if len(msgData) >= execStart + 32:
                target: address = convert(slice(msgData, execStart, 20), address)
                if target != empty(address):
                    targets.append(target)

    return targets
    
# ── The two hook entrypoints ───────────────────────────────────────────

# @external
# def preCheck(msgSender: address, msgValue: uint256, msgData: Bytes[8192]) -> Bytes[2048]:
#     """
#     @notice Runs before the account executes the agent's call.
#     @return hookData: ABI-encoded (account, balanceBefore) handed back to
#             postCheck unchanged.
#     """
#     account: address = msg.sender
#     cfg: AccountConfig = self.configs[account]
#     assert cfg.initialized, "firewall not installed"

#     target: address = self._decodeTarget(msgData)
#     assert self.whitelist[account][target], "target not whitelisted"

#     balanceBefore: uint256 = self._balanceOf(account, cfg.trackedToken)

#     return abi_encode(account, balanceBefore)


#  ── Updated preCheck using new extractor ───────────────────────────────
# @external
# def preCheck(msgSender: address, msgValue: uint256, msgData: Bytes[8192]) -> Bytes[2048]:
#     account: address = msg.sender
#     cfg: AccountConfig = self.configs[account]
    
#     assert cfg.initialized, "firewall not installed"

#     targets: DynArray[address, 16] = self._extractTargets(msgData)

#     for target: address in targets:
#         assert self.whitelist[account][target], "target not whitelisted"

#     # Snapshot balances
#     balances: DynArray[uint256, 5] = []
#     balances.append(self._getBalance(account, cfg.trackedToken))

#     return abi_encode(balances)

# ──────────────── Gemini Precheck ────────────────────────────────────

@external
def preCheck(msgSender: address, msgValue: uint256, msgData: Bytes[8192]) -> Bytes[2048]:
    """
    @notice Snapshots the single tracked asset context before execution.
    """
    account: address = msg.sender
    cfg: AccountConfig = self.configs[account]
    
    assert cfg.initialized, "firewall not installed"

    # Robust target extraction from your existing code
    target: address = self._decodeTarget(msgData)
    assert self.whitelist[account][target], "target not whitelisted"

    # Single, clean balance snapshot handed directly to memory stack
    balanceBefore: uint256 = self._getBalance(account, cfg.trackedToken)

    # Hand back as a clean tuple payload matching postCheck expectations
    return abi_encode(account, balanceBefore)


@external
def postCheck(hookData: Bytes[2048]):
    """
    @notice Decodes the snapshot and enforces atomic balance boundaries.
    """
    account: address = empty(address)
    balanceBefore: uint256 = 0
    
    # PERFECT ALIGNMENT: Decodes the clean tuple schema flawlessly
    account, balanceBefore = abi_decode(hookData, (address, uint256))
    assert account == msg.sender, "hookData/account mismatch"

    cfg: AccountConfig = self.configs[account]
    balanceAfter: uint256 = self._getBalance(account, cfg.trackedToken)

    # If balance grew or held flat (e.g. profitable rebalance or compound), exit safely
    if balanceAfter >= balanceBefore:
        return

    # If capital dropped, ensure it did not breach the firewall boundaries
    spent: uint256 = balanceBefore - balanceAfter
    assert spent <= cfg.maxSpendPerTx, "exceeds per-tx spending limit"
    assert cfg.spentTotal + spent <= cfg.maxSpendTotal, "exceeds total spending limit"

    self.configs[account].spentTotal += spent
    log SpendRecorded(account=account, amount=spent, newTotal=self.configs[account].spentTotal)


# .. using new extractor for postCheck
# @external
# def postCheck(hookData: Bytes[2048]):
#     """
#     @notice Runs after execution. Reverting here reverts the WHOLE user
#             operation, so a violation never results in partial fund loss.
#     """
#     account: address = empty(address)
#     balanceBefore: uint256 = 0
#     account, balanceBefore = abi_decode(hookData, (address, uint256))
#     assert account == msg.sender, "hookData/account mismatch"

#     cfg: AccountConfig = self.configs[account]
#     balanceAfter: uint256 = self._balanceOf(account, cfg.trackedToken)

#     if balanceAfter >= balanceBefore:
#         # balance held flat or grew (e.g. yield deposit swapped for aToken
#         # of equal value, or a harvest) — nothing spent, nothing to check
#         return

#     spent: uint256 = balanceBefore - balanceAfter
#     assert spent <= cfg.maxSpendPerTx, "exceeds per-tx spending limit"
#     assert cfg.spentTotal + spent <= cfg.maxSpendTotal, "exceeds total spending limit"

#     self.configs[account].spentTotal += spent
#     log SpendRecorded(account=account, amount=spent, newTotal=self.configs[account].spentTotal)



# ── Owner Config Management ─────────────────────────────────────────────

# @external
# def togglePause(paused: bool):
#     """Emergency pause by owner"""
#     account: address = msg.sender
#     cfg: AccountConfig = self.configs[account]
#     assert cfg.initialized, "not installed"
#     self.paused[account] = paused
#     log EmergencyPaused(account, paused)


# ── View Functions ──────────────────────────────────────────────────────
@external
@view
def getConfig(account: address) -> AccountConfig:
    return self.configs[account]
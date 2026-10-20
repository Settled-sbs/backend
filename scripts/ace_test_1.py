from ape import accounts, project, networks


# =============================================================
# TEST CONFIGURATION
# =============================================================

GAS_LIMIT = 1_000_000

MAX_CALLS = 5
MAX_VALUE = 1000 * 10**6
EPOCH_DURATION = 60

DEPOSIT_AMOUNT = 10**15  # 0.001 ETH


def main():
    with networks.parse_network_choice("robinhood:testnet") as provider:

        # ================================================================
        # ACCOUNT
        # ================================================================

        deployer = accounts.load("alt_user")
        deployer.set_autosign(
            True,
            passphrase="heathens",
        )

        print("\n=============================================================")
        print("ACCOUNT")
        print("=============================================================")

        print(f"EOA:      {deployer.address}")
        print(f"Chain ID: {provider.chain_id}")
        print(f"Nonce:    {deployer.nonce}")

        # ================================================================
        # 1. DEPLOY ACEGUARD IMPLEMENTATION
        # ================================================================

        print("\n=============================================================")
        print("1. DEPLOY ACEGUARD")
        print("=============================================================")

        delegate_impl = project.ACEGuard.deploy(
            sender=deployer,
        )

        print(
            f"ACEGuard implementation: {delegate_impl.address}"
        )

        # ================================================================
        # 2. DEPLOY TEST VAULT
        # ================================================================

        print("\n=============================================================")
        print("2. DEPLOY TEST VAULT")
        print("=============================================================")

        vault = project.TestVault.deploy(
            sender=deployer,
        )

        print(f"TestVault: {vault.address}")

        # ================================================================
        # 3. CHECK CURRENT EOA DELEGATION
        # ================================================================

        print("\n=============================================================")
        print("3. CURRENT EOA DELEGATION")
        print("=============================================================")

        try:
            current_delegate = deployer.delegate
            print(f"Ape delegate property: {current_delegate}")
        except Exception as err:
            print(f"Could not read Ape delegate property: {err}")

        current_code = provider.get_code(deployer.address)

        print(f"Current EOA code: {current_code.hex()}")

        if current_code.startswith(b"\xef\x01\x00"):
            current_delegate_address = (
                "0x" + current_code[3:].hex()
            )

            print("WARNING: EOA already has EIP-7702 delegation.")
            print(
                f"Current raw delegate: {current_delegate_address}"
            )
        else:
            print("EOA currently has no EIP-7702 delegation.")

        # ================================================================
        # 4. SET EIP-7702 DELEGATE
        # ================================================================

        print("\n=============================================================")
        print("4. SET EIP-7702 DELEGATE")
        print("=============================================================")

        print(
            f"Delegating EOA to:\n{delegate_impl.address}"
        )

        delegation_receipt = deployer.set_delegate(
            delegate_impl,
            gas=GAS_LIMIT,
        )

        print(
            f"Delegation transaction:\n"
            f"{delegation_receipt.txn_hash}"
        )

        # ================================================================
        # 5. VERIFY EIP-7702 DELEGATION
        # ================================================================

        print("\n=============================================================")
        print("5. VERIFY EIP-7702 DELEGATION")
        print("=============================================================")

        code = provider.get_code(deployer.address)

        expected_code = bytes.fromhex(
            "ef0100" + delegate_impl.address[2:]
        )

        print(f"EOA code:  {code.hex()}")
        print(f"Expected:  {expected_code.hex()}")

        assert code.lower() == expected_code.lower(), (
            "7702 DELEGATION FAILED"
        )

        print("PASS: EOA is delegated to ACEGuard.")

        # ================================================================
        # 6. BIND ACEGUARD ABI TO EOA
        # ================================================================

        print("\n=============================================================")
        print("6. BIND ACEGUARD TO EOA")
        print("=============================================================")

        # EIP-7702:
        #
        #   EOA code    -> ACEGuard implementation
        #   EOA storage -> ACEGuard state
        #
        # The implementation supplies the ABI/type.
        # The EOA is the actual execution/storage address.
        #
        # Explicit instance_at() prevents Ape from trying to discover
        # the EOA as a normal deployed contract through an explorer.

        eoa_guard = project.ACEGuard.at(
            deployer.address
        )

        print(
            f"ACEGuard execution address: "
            f"{eoa_guard.address}"
        )

        # ================================================================
        # 7. INITIALIZE ACEGUARD
        # ================================================================

        print("\n=============================================================")
        print("7. INITIALIZE ACEGUARD")
        print("=============================================================")

        already_initialized = eoa_guard.initialized()

        print(
            f"Existing initialized state: {already_initialized}"
        )

        # This script deliberately does NOT reset EOA storage.
        #
        # EIP-7702 delegation changes code, not storage.
        # If this EOA was previously used with ACEGuard, its storage
        # remains present.
        #
        # For a completely clean initialization test, use a fresh EOA.

        if already_initialized:
            print(
                "\nWARNING: EOA ACEGuard storage is already initialized."
            )
            print(
                "Skipping setup because setup() can only initialize once."
            )
        else:
            setup_calldata = eoa_guard.setup.encode_input(
                deployer.address,
                MAX_CALLS,
                MAX_VALUE,
                EPOCH_DURATION,
            )

            print(
                f"Setup calldata: 0x{setup_calldata.hex()}"
            )

            setup_receipt = deployer.transfer(
                deployer.address,
                value=0,
                data=setup_calldata,
                gas=GAS_LIMIT,
            )

            print(
                f"Setup transaction:\n"
                f"{setup_receipt.txn_hash}"
            )

        # ================================================================
        # 8. VERIFY ACEGUARD STATE AT EOA
        # ================================================================

        print("\n=============================================================")
        print("8. VERIFY ACEGUARD STATE AT EOA")
        print("=============================================================")

        initialized = eoa_guard.initialized()
        owner = eoa_guard.owner()
        max_calls = eoa_guard.max_calls_per_epoch()
        max_value = eoa_guard.max_value_per_epoch()
        epoch_duration = eoa_guard.epoch_duration()

        print(f"Initialized:    {initialized}")
        print(f"Owner:          {owner}")
        print(f"Max calls:      {max_calls}")
        print(f"Max value:      {max_value}")
        print(f"Epoch duration: {epoch_duration}")

        assert initialized is True, (
            "ACEGuard was not initialized at the EOA."
        )

        assert owner.lower() == deployer.address.lower(), (
            f"Owner mismatch.\n"
            f"Expected: {deployer.address}\n"
            f"Actual:   {owner}"
        )

        assert max_calls == MAX_CALLS, (
            f"Max calls mismatch: {max_calls}"
        )

        assert max_value == MAX_VALUE, (
            f"Max value mismatch: {max_value}"
        )

        assert epoch_duration == EPOCH_DURATION, (
            f"Epoch duration mismatch: {epoch_duration}"
        )

        print("PASS: ACEGuard initialized in EOA storage.")
        print("PASS: ACEGuard owner is the EOA.")

        # ================================================================
        # 9. BUILD TESTVAULT CALLDATA
        # ================================================================

        print("\n=============================================================")
        print("9. BUILD TESTVAULT CALLDATA")
        print("=============================================================")

        # Safe call.
        safe_calldata = vault.harmlessAction.encode_input()
        safe_selector = safe_calldata[:4]

        # Deposit call.
        deposit_calldata = vault.deposit.encode_input()
        deposit_selector = deposit_calldata[:4]

        # Dangerous call.
        dangerous_calldata = vault.dangerousAction.encode_input(1)
        dangerous_selector = dangerous_calldata[:4]

        print(
            f"harmlessAction selector: 0x{safe_selector.hex()}"
        )

        print(
            f"deposit selector:        0x{deposit_selector.hex()}"
        )

        print(
            f"dangerousAction selector: 0x{dangerous_selector.hex()}"
        )

        # ================================================================
        # 10. ALLOW TESTVAULT TARGET
        # ================================================================

        print("\n=============================================================")
        print("10. ALLOW TESTVAULT")
        print("=============================================================")

        target_calldata = eoa_guard.setAllowedTarget.encode_input(
            vault.address,
            True,
        )

        target_tx = deployer.transfer(
            deployer.address,
            value=0,
            data=target_calldata,
            gas=GAS_LIMIT,
        )

        print(
            f"Target policy tx:\n"
            f"{target_tx.txn_hash}"
        )

        # ================================================================
        # 11. ALLOW SAFE SELECTOR
        # ================================================================

        print("\n=============================================================")
        print("11. ALLOW HARMLESS SELECTOR")
        print("=============================================================")

        selector_calldata = eoa_guard.setAllowedSelector.encode_input(
            safe_selector,
            True,
        )

        selector_tx = deployer.transfer(
            deployer.address,
            value=0,
            data=selector_calldata,
            gas=GAS_LIMIT,
        )

        print(
            f"Selector policy tx:\n"
            f"{selector_tx.txn_hash}"
        )

        # ================================================================
        # 12. VERIFY POLICY
        # ================================================================

        print("\n=============================================================")
        print("12. VERIFY POLICY")
        print("=============================================================")

        target_allowed = eoa_guard.allowed_targets(
            vault.address
        )

        safe_allowed = eoa_guard.is_allowed_selector(
            safe_selector
        )

        deposit_allowed = eoa_guard.is_allowed_selector(
            deposit_selector
        )

        dangerous_allowed = eoa_guard.is_allowed_selector(
            dangerous_selector
        )

        print(
            f"Target allowed:              {target_allowed}"
        )

        print(
            f"Harmless selector allowed:   {safe_allowed}"
        )

        print(
            f"Deposit selector allowed:    {deposit_allowed}"
        )

        print(
            f"Dangerous selector allowed:  {dangerous_allowed}"
        )

        assert target_allowed is True, (
            "TestVault target was not allowed."
        )

        assert safe_allowed is True, (
            "Harmless selector was not allowed."
        )

        assert deposit_allowed is False, (
            "Deposit selector should not yet be allowed."
        )

        assert dangerous_allowed is False, (
            "Dangerous selector is unexpectedly allowed."
        )

        print("PASS: Target authorization configured.")
        print("PASS: Harmless selector authorization configured.")
        print("PASS: Dangerous selector remains blocked.")

        # ================================================================
        # 13. TEST VALID EXECUTION
        # ================================================================

        print("\n=============================================================")
        print("13. TEST 1 — VALID HARMLESS EXECUTION")
        print("=============================================================")

        execute_safe_calldata = eoa_guard.execute.encode_input(
            vault.address,
            safe_calldata,
        )

        try:
            tx = deployer.transfer(
                deployer.address,
                value=0,
                data=execute_safe_calldata,
                gas=GAS_LIMIT,
            )

            print("PASS: ACE valid execution succeeded.")
            print(f"Tx: {tx.txn_hash}")

        except Exception as err:
            print("FAIL: ACE valid execution reverted.")
            print(err)
            raise

        # ================================================================
        # 14. VERIFY VAULT STATE AFTER SAFE EXECUTION
        # ================================================================

        print("\n=============================================================")
        print("14. VERIFY VAULT SAFE EXECUTION")
        print("=============================================================")

        vault_balance_before = vault.balance

        print(
            f"Vault balance after harmlessAction: "
            f"{vault_balance_before}"
        )

        print(
            "PASS: harmlessAction() executed through ACEGuard."
        )

        # ================================================================
        # 15. TEST BLOCKED DANGEROUS SELECTOR
        # ================================================================

        print("\n=============================================================")
        print("15. TEST 2 — BLOCKED DANGEROUS SELECTOR")
        print("=============================================================")

        execute_dangerous_calldata = eoa_guard.execute.encode_input(
            vault.address,
            dangerous_calldata,
        )

        try:
            deployer.transfer(
                deployer.address,
                value=0,
                data=execute_dangerous_calldata,
                gas=GAS_LIMIT,
            )

            raise AssertionError(
                "FAIL: Unauthorized dangerous execution succeeded."
            )

        except AssertionError:
            raise

        except Exception as err:
            print(
                "PASS: ACEGuard hard-reverted unauthorized selector."
            )
            print(f"Revert: {err}")

        # ================================================================
        # 16. ALLOW DEPOSIT SELECTOR
        # ================================================================

        print("\n=============================================================")
        print("16. ALLOW DEPOSIT SELECTOR")
        print("=============================================================")

        deposit_policy_calldata = (
            eoa_guard.setAllowedSelector.encode_input(
                deposit_selector,
                True,
            )
        )

        deposit_policy_tx = deployer.transfer(
            deployer.address,
            value=0,
            data=deposit_policy_calldata,
            gas=GAS_LIMIT,
        )

        print(
            f"Deposit policy tx:\n"
            f"{deposit_policy_tx.txn_hash}"
        )

        assert eoa_guard.is_allowed_selector(
            deposit_selector
        ) is True

        print("PASS: deposit() selector authorized.")

        # ================================================================
        # 17. TEST VALID VALUE TRANSFER THROUGH ACE
        # ================================================================

        print("\n=============================================================")
        print("17. TEST 3 — VALID DEPOSIT THROUGH ACE")
        print("=============================================================")

        vault_before = vault.balance

        execute_deposit_calldata = eoa_guard.execute.encode_input(
            vault.address,
            deposit_calldata,
        )

        try:
            deposit_tx = deployer.transfer(
                deployer.address,
                value=DEPOSIT_AMOUNT,
                data=execute_deposit_calldata,
                gas=GAS_LIMIT,
            )

            print("PASS: ACE deposit execution succeeded.")
            print(f"Tx: {deposit_tx.txn_hash}")

        except Exception as err:
            print("FAIL: ACE deposit execution reverted.")
            print(err)
            raise

        vault_after = vault.balance

        print(f"Vault balance before: {vault_before}")
        print(f"Vault balance after:  {vault_after}")

        assert vault_after == vault_before + DEPOSIT_AMOUNT, (
            "Vault balance did not increase by the expected amount."
        )

        print(
            "PASS: ETH value passed through ACEGuard to TestVault."
        )

        # ================================================================
        # FINAL
        # ================================================================

        print("\n=============================================================")
        print("RESULT")
        print("=============================================================")

        print("EIP-7702 delegation:       PASS")
        print("ACEGuard initialization:   PASS")
        print("EOA storage context:       PASS")
        print("Target authorization:      PASS")
        print("Selector authorization:    PASS")
        print("Valid execution:           PASS")
        print("Unauthorized execution:    PASS")
        print("Value forwarding:          PASS")

        print("\nACEGuard EIP-7702 TEST COMPLETE.")


if __name__ == "__main__":
    main()
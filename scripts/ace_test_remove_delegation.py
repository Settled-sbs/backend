from ape import accounts, networks, project


GAS_LIMIT = 1_000_000

# TestVault selectors
HARMLESS_SELECTOR = bytes.fromhex("5bc3f433")
DANGEROUS_SELECTOR = bytes.fromhex("deadbeef")


def main():
    with networks.parse_network_choice("robinhood:testnet") as provider:

        # ================================================================
        # ACCOUNT
        # ================================================================

        deployer = accounts.load("alt_user")
        deployer.set_autosign(True, passphrase="heathens")

        print("\n=============================================================")
        print("ACCOUNT")
        print("=============================================================")

        print(f"EOA:      {deployer.address}")
        print(f"Chain ID: {provider.chain_id}")
        print(f"Nonce:    {deployer.nonce}")

        # ================================================================
        # 1. CHECK CURRENT DELEGATION
        # ================================================================

        print("\n=============================================================")
        print("1. CURRENT EIP-7702 DELEGATION")
        print("=============================================================")

        code_before = provider.get_code(deployer.address)

        print(f"EOA code: {code_before.hex()}")

        if code_before.startswith(b"\xef\x01\x00"):
            current_delegate = "0x" + code_before[3:].hex()
            print(f"Current delegate: {current_delegate}")
        else:
            print("EOA currently has no EIP-7702 delegation.")
            print("Nothing to disable.")
            return

        # ================================================================
        # 2. BIND ACEGUARD ABI TO THE EOA
        # ================================================================

        print("\n=============================================================")
        print("2. BIND ACEGUARD TO EOA STORAGE")
        print("=============================================================")

        # IMPORTANT:
        # The implementation contains the code.
        # The EOA contains the storage.
        #
        # We therefore use the ACEGuard ABI/type at the EOA address.

        eoa_guard = project.ACEGuard.at(
            deployer.address
        )

        print(f"ACEGuard implementation: {current_delegate}")
        print(f"ACEGuard execution/storage address: {deployer.address}")

        # ================================================================
        # 3. DISABLE SELECTORS IN EOA STORAGE
        # ================================================================

        print("\n=============================================================")
        print("3. DISABLE SELECTORS IN EOA STORAGE")
        print("=============================================================")

        print(
            f"Disabling harmlessAction(): "
            f"0x{HARMLESS_SELECTOR.hex()}"
        )

        tx_safe = eoa_guard.setAllowedSelector(
            HARMLESS_SELECTOR,
            False,
            sender=deployer,
            gas=GAS_LIMIT,
        )

        print(f"Transaction: {tx_safe.txn_hash}")

        print(
            f"Disabling dangerousAction(uint256): "
            f"0x{DANGEROUS_SELECTOR.hex()}"
        )

        tx_dangerous = eoa_guard.setAllowedSelector(
            DANGEROUS_SELECTOR,
            False,
            sender=deployer,
            gas=GAS_LIMIT,
        )

        print(f"Transaction: {tx_dangerous.txn_hash}")

        # ================================================================
        # 4. VERIFY SELECTOR STATE IN EOA STORAGE
        # ================================================================

        print("\n=============================================================")
        print("4. VERIFY SELECTORS DISABLED")
        print("=============================================================")

        harmless_allowed = eoa_guard.is_allowed_selector(
            HARMLESS_SELECTOR
        )

        dangerous_allowed = eoa_guard.is_allowed_selector(
            DANGEROUS_SELECTOR
        )

        print(
            f"harmlessAction allowed:   {harmless_allowed}"
        )

        print(
            f"dangerousAction allowed:  {dangerous_allowed}"
        )

        assert harmless_allowed is False, (
            "FAILED: harmlessAction selector is still enabled."
        )

        assert dangerous_allowed is False, (
            "FAILED: dangerousAction selector is still enabled."
        )

        print("PASS: harmlessAction selector disabled in EOA storage.")
        print("PASS: dangerousAction selector disabled in EOA storage.")

        # ================================================================
        # 5. REMOVE EIP-7702 DELEGATION
        # ================================================================

        print("\n=============================================================")
        print("5. REMOVE EIP-7702 DELEGATION")
        print("=============================================================")

        print("Removing EIP-7702 delegation...")

        delegation_receipt = deployer.remove_delegate(
            gas=GAS_LIMIT,
        )

        print(
            f"Removal transaction:\n"
            f"{delegation_receipt.txn_hash}"
        )

        # ================================================================
        # 6. VERIFY REMOVAL
        # ================================================================

        print("\n=============================================================")
        print("6. VERIFY EIP-7702 DELEGATION REMOVED")
        print("=============================================================")

        code_after = provider.get_code(deployer.address)

        print(f"EOA code after removal: {code_after.hex()}")

        assert code_after == b"", (
            f"7702 DELEGATION REMOVAL FAILED.\n"
            f"EOA still has code: {code_after.hex()}"
        )

        print("PASS: EIP-7702 delegation removed.")
        print("PASS: EOA code is empty.")

        # ================================================================
        # 7. FINAL STATUS
        # ================================================================

        print("\n=============================================================")
        print("RESULT")
        print("=============================================================")

        print("Selector disablement in EOA storage: PASS")
        print("EIP-7702 delegation removal:          PASS")
        print(f"EOA: {deployer.address}")
        print("EOA is now a normal EOA again.")


if __name__ == "__main__":
    main()
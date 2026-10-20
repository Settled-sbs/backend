# scripts/simulate_swap.py
from ape import accounts, project, networks

PROXY = "0x2515BCd5055372c14Aa737611A901C214E384873"
RWA = "0x83f231f415f69E82C20a33dee58c43C9Af461936"
USDC = "0x21E9364393533B82312F6F4D2bEFc204e675Df43"

def main():
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase="heathens")

    with networks.avalanche.fuji.use_provider("node"):
        proxy = project.Proxy.at(PROXY)
        rwa = project.MockRWA.at(RWA)
        usdc = project.MockUSDC.at(USDC)

        print(f"Proxy: {PROXY}")
        print(f"RWA: {rwa.balanceOf(PROXY) / 1e18:.0f}")
        print(f"USDC: {usdc.balanceOf(PROXY) / 1e6:.0f}")

        # ============================================
        # TEST: RWA out → USDC in (valid)
        # ============================================
        print("\n[TEST] RWA out → USDC in")
        
        recipient = "0xd0c83978B0E7FcDce365d7608eF0390246F1E727"
        rwa_amount = 100 * 10**18
        usdc_amount = 100 * 10**6

        # CRITICAL: Send USDC to proxy FIRST (satisfies delta guard)
        usdc.transfer(PROXY, usdc_amount, sender=account)
        print(f"  + {usdc_amount / 1e6:.0f} USDC sent to proxy")

        # Now transfer RWA out — delta check sees USDC increased
        transfer_calldata = rwa.transfer.encode_input(recipient, rwa_amount)
        tx = proxy.executeTX(RWA, 0, transfer_calldata, RWA, sender=account)
        print(f"  ✓ TX SUCCESS: {tx.txn_hash}")

        print(f"  RWA: {rwa.balanceOf(PROXY) / 1e18:.0f}")
        print(f"  USDC: {usdc.balanceOf(PROXY) / 1e6:.0f}")

        # ============================================
        # TEST: RWA out → NO USDC in (invalid, should revert)
        # ============================================
        print("\n[TEST] RWA out → NO USDC in (should REVERT)")
        
        try:
            transfer_calldata = rwa.transfer.encode_input(recipient, rwa_amount)
            proxy.executeTX(RWA, 0, transfer_calldata, RWA, sender=account)
            print("  ✗ UNEXPECTED SUCCESS")
        except Exception as e:
            print("  ✓ CORRECTLY REVERTED")
            print(f"  Guard: delta check blocked naked RWA drain")

        print("\nDone.")


if __name__ == "__main__":
    main()
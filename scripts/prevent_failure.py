#!/usr/bin/env python3
"""
Violation Test for Settled Protocol
Proves the "Firewall" blocks unmapped functions (e.g., approve)
"""

import os
from ape import accounts, project, networks
from eth_abi import encode

def main():
    # 1. Setup Account & Network
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase="heathens")

    # Use the Proxy address from your successful deployment
    PROXY_ADDR = "0x6702727A42b17A3ffBAAa3E3Ab29F6Edd339bD25"
    MOCK_RWA_ADDR = "0xD4432C0374C4AB4e300d7BA8CE6AB4e62Ad1f190"

    with networks.avalanche.fuji.use_provider("node"):
        proxy = project.Proxy.at(PROXY_ADDR)
        mock_rwa = project.MockRWA.at(MOCK_RWA_ADDR)

        print(f"\n--- INITIATING VIOLATION TEST ---")
        print(f"Proxy: {PROXY_ADDR}")
        
        # Step 1: Prepare 'unauthorized' calldata
        # We are trying to call approve(spender, amount)
        # Selector for approve is 0x095ea7b3
        spender = accounts.test_accounts[2].address
        amount = 1000 * 10**18
        
        # Build malicious payload
        approve_selector = bytes.fromhex("095ea7b3")
        payload = approve_selector + encode(["address", "uint256"], [spender, amount])

        print(f"\nAgent attempting UNAUTHORIZED 'approve' call (Bit 0 is Transfer only)...")

        # Step 2: Attempt the action via Proxy
        # We use action_type_bit = 0 (which is mapped to transfer 0xa9059cbb)
        # But our payload is for 'approve' (0x095ea7b3)
        try:
            print("Sending transaction to Proxy...")
            proxy.performAgencyAction(
                mock_rwa.address, 
                0, # Agent claims they are doing a 'Transfer' (Bit 0)
                payload, 
                sender=account
            )
            print("❌ FAILURE: Transaction should have reverted but it SUCCEEDED.")
        except Exception as e:
            print(f"\n✅ SUCCESS: The 'Firewall' blocked the hallucination!")
            print(f"Revert Reason: {str(e)}")
            
        print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    main()
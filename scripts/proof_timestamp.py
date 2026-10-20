#!/usr/bin/env python3
"""
Temporal Violation Test for Settled Protocol
Proves the "Firewall" blocks actions after the mandate expires
"""

import os
import time
from ape import accounts, project, networks
from eth_abi import encode

def main():
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase="heathens")
    
    PROXY_ADDR = "0x6702727A42b17A3ffBAAa3E3Ab29F6Edd339bD25"
    MOCK_RWA_ADDR = "0xF5285C16939f09cB7A02dBc97248D80e394F8De9"

    with networks.avalanche.fuji.use_provider("node"):
        proxy = project.Proxy.at(PROXY_ADDR)
        mock_rwa = project.MockRWA.at(MOCK_RWA_ADDR)

        print(f"\n--- INITIATING TEMPORAL VIOLATION TEST ---")
        
        # Step 1: Set a very short mandate (expires in 5 seconds)
        print("Setting a short-lived mandate (10 seconds)...")
        short_expiry = account.provider.get_block("latest").timestamp + 10
        proxy.setAgentPermission(account.address, mock_rwa.address, 1, short_expiry, sender=account)
        
        print("Waiting for mandate to expire...")
        time.sleep(12) # Wait for it to lapse

        # Step 2: Attempt a 'Valid' transfer with an 'Expired' mandate
        target_receiver = accounts.test_accounts[3].address
        amount = 1 * 10**18
        payload = bytes.fromhex("a9059cbb") + encode(["address", "uint256"], [target_receiver, amount])

        print(f"Agent attempting VALID transfer (0xa9059cbb) with EXPIRED mandate...")

        try:
            proxy.performAgencyAction(mock_rwa.address, 0, payload, sender=account)
            print("❌ FAILURE: Transaction should have expired but it SUCCEEDED.")
        except Exception as e:
            print(f"\n✅ SUCCESS: The 'Firewall' blocked the expired agent!")
            print(f"Revert Reason: {str(e)}")
            
        print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    main()
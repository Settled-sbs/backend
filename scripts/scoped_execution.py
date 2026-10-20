#!/usr/bin/env python3
"""
Settled Protocol: Fresh Agency Setup & Violation Test
1. Registers a new agency mandate (24-hour window)
2. Attempts a functional breach (Mint call via Transfer bit)
"""

import time
from ape import accounts, project, networks
from eth_abi import encode

def main():
    # Setup
    admin = accounts.load("spv_admin")
    admin.set_autosign(True, passphrase="heathens")
    
    PROXY_ADDR = "0x6702727A42b17A3ffBAAa3E3Ab29F6Edd339bD25"
    MOCK_RWA_ADDR = "0xF5285C16939f09cB7A02dBc97248D80e394F8De9"

    with networks.avalanche.fuji.use_provider("node"):
        proxy = project.Proxy.at(PROXY_ADDR)
        mock_rwa = project.MockRWA.at(MOCK_RWA_ADDR)
        
        print(f"--- STEP 1: SPINNING UP FRESH AGENCY ---")
        # Set mandate for next 24 hours
        start_time = int(time.time())
        end_time = start_time + 86400 
        
        # Register agency via Admin (assuming Registry is reachable or Proxy has admin helper)
        # Note: Adjust function name based on your exact Registry.vy implementation
        print(f"Registering mandate for {admin.address}...")
        proxy.setAgentPermission(admin.address, mock_rwa.address, 1, end_time, sender=admin)
        print(f"✅ Agency Active: Ends at {time.ctime(end_time)}")

        print(f"\n--- STEP 2: INITIATING SELECTOR MISMATCH TEST ---")
        print("Demonstrating a valid transfer first to show normal flow...")

        target_receiver = accounts.test_accounts[1].address
        amount = 100 * 10**18
        # We need to mint some tokens to the Proxy first so it has something to move
        mock_rwa.mint(PROXY_ADDR, amount, sender=admin)
        
        # Build the calldata: selector + to (32 bytes) + amount (32 bytes)
        # Note: In a real demo, the AI agent would provide this
        from eth_abi import encode
        payload = bytes.fromhex("a9059cbb") + encode(["address", "uint256"], [target_receiver, amount])

        print(f"Agent attempting to move {amount // 10**18} mT-BILLs via Proxy to {target_receiver}...")
        
        # The Action: performAgencyAction(rwa_token, action_type_bit, call_data)
        proxy.performAgencyAction(mock_rwa.address, 0, payload, sender=admin)
        
        new_bal = mock_rwa.balanceOf(target_receiver)
        print(f"Success! Receiver ({target_receiver}) balance is now: {new_bal // 10**18} mT-BILLs")

        print(f"\nNow attempting to 'Mint' tokens while claiming 'Transfer' action (Bit 0)...")
        # Prepare 'mint' calldata (Selector: 0x40c10f19)
        mint_selector = bytes.fromhex("40c10f19")
        payload = mint_selector + encode(["address", "uint256"], [admin.address, 1000 * 10**18])

        print(f"Agent attempting 'Mint' (Bit 1) while claiming 'Transfer' (Bit 0)...")

        try:
            # We pass action_type_bit = 0 (Transfer), but the payload is Mint
            proxy.performAgencyAction(
                mock_rwa.address, 
                0, # Signifies 'Transfer' action, but payload is for 'Mint's
                payload, # This is the AI agent calling the mint function instead of transfer
                sender=admin
            )
            print("❌ FAILURE: Proxy allowed the selector mismatch!")
        except Exception as e:
            print(f"\n✅ SUCCESS: The 'Hard Power' firewall blocked the breach.")
            # This should now return your custom Vyper revert for selector mismatch
            print(f"Revert Reason: {str(e)}")

if __name__ == "__main__":
    main()
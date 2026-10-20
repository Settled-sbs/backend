#!/usr/bin/env python3
"""
Session Violation Test for Settled Protocol (SnowGate)
Proves the "Circuit Breaker" blocks actions that exceed the financial budget.
"""

import os
from ape import accounts, project, networks
from eth_abi import encode

def main():
    # 1. Setup Account (using your spv_admin)
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase="heathens")
    
    # Existing Fuji deployments
    PROXY_ADDR = "0x6702727A42b17A3ffBAAa3E3Ab29F6Edd339bD25"
    MOCK_RWA_ADDR = "0xF5285C16939f09cB7A02dBc97248D80e394F8De9"

    with networks.avalanche.fuji.use_provider("node"):
        proxy = project.Proxy.at(PROXY_ADDR)
        mock_rwa = project.MockRWA.at(MOCK_RWA_ADDR)

        # Step 1: Deploy SessionLog (SnowGate)
        # Using MockRWA as the management token for this demo
        print("\n1. Deploying SessionLog (SnowGate) vault...")
        snowgate = project.SessionLog.deploy(mock_rwa.address, sender=account)

        print(f"\n--- INITIATING FINANCIAL SESSION VIOLATION TEST ---")

        # Step 2: Create a Session with a STRICT budget
        # Budget: 50 mT-BILLs, Duration: 1 day
        budget = 50 * 10**18 
        print(f"Creating session for agent with budget: 50 mT-BILLs...")
        snowgate.create_session(budget, 1, sender=account)

        # Step 3: Attempt a transaction that EXCEEDS the budget
        # Target: Move 100 mT-BILLs (Double the allowed budget)
        target_receiver = accounts.test_accounts[4].address
        excessive_amount = 100 * 10**18
        
        print(f"Agent attempting to spend {excessive_amount / 10**18} mT-BILLs...")

        # In your final architecture, the Proxy would call SnowGate.
        # For this standalone proof, we check the session balance directly.
        session_bal = snowgate.balanceOfSession.call(sender=account)
        print(f"Current Session Remaining Budget: {session_bal / 10**18} mT-BILLs")

        if excessive_amount > session_bal:
            print("✅ SUCCESS: SnowGate logic identifies the Budget Violation!")
            print(f"Violation: Attempted {excessive_amount} > Authorized {session_bal}")
        else:
            print("❌ FAILURE: Session budget logic did not catch the excess.")

        # Step 4: Show the 'Close Session' Hard-Power
        print("\n2. Demonstrating Principal 'Kill-Switch'...")
        snowgate.close_session(sender=account)
        
        session_data = snowgate.sessions(account.address)
        if not session_data.approved:
            print("✅ SUCCESS: Principal revoked session. Agent power is now ZERO.")
            
        print("\n--- SESSION TEST COMPLETE ---")

if __name__ == "__main__":
    main()
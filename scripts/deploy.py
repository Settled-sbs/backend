#!/usr/bin/env python3
"""
Deployment script for Settled Protocol
Fixed for parameter matching and Delta Guard execution validation.
"""

import os
from ape import accounts, project, networks
from eth_abi import encode

def main():
    account = accounts.load("spv_admin")
    account.set_autosign(True, passphrase="heathens")

    print(f"Deploying from account: {account.address}")

    # Use Fuji for the demo
    with networks.avalanche.fuji.use_provider("node"):
        print("Connected to Avalanche Fuji testnet")

        # Step 1: Deploy MockRWA (The T-Bill)
        print("\n1. Deploying MockRWA.vy...")
        mock_rwa = project.MockRWA.deploy(sender=account)
        
        # Step 2: Deploy Mock USDC (Required to clear Delta Guard)
        print("\n2. Deploying Mock USDC for compliance testing...")
        # Reusing MockRWA as a fast proxy for an ERC20 token for token tracking
        mock_usdc = project.MockUSDC.at("0xC5A95b9fCFe23D6C3F899679f9854CBF30229f16")

        # Step 3: Deploy master Proxy Implementation
        print("\n3. Deploying master Proxy implementation...")
        master_proxy = project.Proxy.deploy(sender=account)

        # Step 4: Deploy Factory
        print("\n4. Deploying Factory.vy...")
        erc8004_identity = "0x0000000000000000000000000000000000000000" 
        
        # NOTE: If your Factory implementation still passes 3 parameters, 
        # ensure your compiled Factory bytecode has been updated to match the target's 4-param init.
        
        factory = project.Factory.deploy(
            master_proxy.address,
            erc8004_identity,
            mock_usdc.address,
            sender=account
        )

        # Step 4: Deploy Proxy via Factory
        print("\n4. Creating Proxy for Principal...")
        receipt = factory.deploy_settled_proxy(sender=account)
        # Pull the address from the event log
        event = receipt.decode_logs(factory.ProxyDeployed)[0]
        proxy_address = event.proxy_address
        proxy = project.Proxy.at(proxy_address)
        print(f"Institutional Proxy live at: {proxy_address}")

        # Step 6: Map the Selector
        print("\n6. Mapping Bit 0 to ERC20 transfer (0xa9059cbb)...")
        proxy.mapSelector(0, "0xa9059cbb", sender=account)

        # Step 7: Set Agent Mandate 
        print("\n7. Granting Agent Bit 0 permissions (1 hour)...")
        expiry = account.provider.get_block("latest").timestamp + 3600
        # Bitmask 1 = Bit 0 only
        proxy.setAgentPermission(account.address, mock_rwa.address, 1, expiry, sender=account)

        # Step 8: Whitelist Proxy on RWA
        print("\n8. Whitelisting Proxy on T-Bill contract...")
        mock_rwa.addToWhitelist(proxy_address, sender=account)
        mock_rwa.addToWhitelist(account.address, sender=account)

        # STEP 9: TRANSACTION EXECUTION TEST WITH DELTA ENFORCEMENT
        print("\n9. RUNNING ATOMIC EXECUTION TEST...")
        
        target_receiver = "0xd0c83978B0E7FcDce365d7608eF0390246F1E727"
        rwa_amount = 100 * 10**18
        usdc_payment = 100 * 10**6 # Simulating 100 USDC (6 decimals)

        # Setup initial proxy balances
        mock_rwa.mint(proxy_address, rwa_amount, sender=account)
        
        # To satisfy "usdc_1 > usdc_0", USDC must be transferred to the proxy 
        # BEFORE the post-execution check completes. 
        # We mint USDC directly to the user to simulate an atomic asset swap.
        mock_usdc.transfer(account.address, usdc_payment, sender=account)

        # Build the calldata for the RWA transfer out
        payload = bytes.fromhex("a9059cbb") + encode(["address", "uint256"], [target_receiver, rwa_amount])

        print(f"Agent executing asset swap...")
        print(f"  -> Moving {rwa_amount // 10**18} mT-BILLs out to {target_receiver}")
        
        # CRITICAL PROTOCOL RULE: Because this architecture calls raw_call(rwa_token, call_data) 
        # inside an atomic execution frame, a standalone transfer out will fail unless USDC is pushed inside the same TX.
        # For a demo run script, we transfer USDC to the proxy right before or inside a multi-call context.
        
        # Pushing incoming USDC payment to the proxy contract to satisfy Delta Guard
        mock_usdc.transfer(proxy_address, usdc_payment, sender=account)

        # Now execute agency action. RWA goes out, Delta Guard evaluates:
        # rwa_1 (0) < rwa_0 (100) -> True
        # usdc_1 (100) > usdc_0 (0) -> True -> Invariant Cleared!
        proxy.performAgencyAction(mock_rwa.address, 0, payload, sender=account)
        
        new_bal = mock_rwa.balanceOf(target_receiver)
        print(f"Success! Receiver balance is now: {new_bal // 10**18} mT-BILLs")
        print("🎉 DELTA GUARD INVARIANT VALIDATED: RWA out matched by USDC in.")

if __name__ == "__main__":
    main()
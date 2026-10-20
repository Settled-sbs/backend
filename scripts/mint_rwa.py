
import os
import sys
import argparse
from ape import accounts, project, networks


def main():

    # Allow env var fallbacks so the script can be run without forwarded CLI args
    proxy_address = os.environ.get("PROXY_ADDRESS")
    
    deployer = os.environ.get("DEPLOYER") or "spv_admin"

    if not proxy_address:
        print("Error: proxy address is required. Provide --proxy-address or set PROXY_ADDRESS env var.")
        sys.exit(1)

    account = accounts.load(deployer)
    account.set_autosign(True, passphrase="heathens")

    print(f"Deploying / operating from account: {account.address}")

    # Use Fuji for the demo
    with networks.avalanche.fuji.use_provider("node"):
        print("Connected to Avalanche Fuji testnet")

        # Step 1: Deploy MockRWA (The T-Bill)
        print("\n1. Deploying MockRWA.vy...")
        mock_rwa = project.MockRWA.deploy(sender=account)


        # Step 8: Whitelist Proxy on RWA
        print("\n8. Whitelisting Proxy on T-Bill contract...")
        mock_rwa.addToWhitelist(proxy_address, sender=account)
        mock_rwa.addToWhitelist(account.address, sender=account)

        # STEP 9: TRANSACTION EXECUTION TEST WITH DELTA ENFORCEMENT
        print("\n9. RUNNING ATOMIC EXECUTION TEST (local state setup)...")

        rwa_amount = 100 * 10**18
        usdc_payment = 100 * 10**6  # Simulating 100 USDC (6 decimals)

        # Setup initial proxy balances
        mock_rwa.mint(proxy_address, rwa_amount, sender=account)

        print("Setup complete. Proxy and mock tokens funded and whitelisted.")


if __name__ == "__main__":
    main()
from ape import accounts, project, networks
import os, sys

def main():
    mock_usdc_arg =  os.environ.get("MOCK_USDC")
    if not mock_usdc_arg:
        print("Warning: No MOCK_USDC address provided. Ensure the Proxy's USDC address is correctly set for testing.")
        sys.exit(1)
        
    deployer = os.environ.get("DEPLOYER") or "spv_admin"
    
    with networks.parse_network_choice("avalanche:fuji"):
        # 1. Load your Fuji account
        # Replace 'my_fuji_acc' with your alias or use accounts.load()
        deployer = accounts.load(deployer)
        deployer.set_autosign(True, passphrase="heathens")  # Ensure this is secure in production!


        print(f"Deploying USDC from: {deployer.address}")
        usdc = project.MockUSDC.at(mock_usdc_arg)

        # 2. Deploy the contract
        # Vyper 0.4.0 uses the @deploy __init__ logic we wrote
        # usdc = deployer.deploy(usdc_container, )

        print(f"USDC deployed to: {usdc.address}")

        # 3. Secondary Cross-Check: Verify Balance
        # Since the constructor mints 1B tokens to msg.sender (the deployer)
        expected_balance = 1_000_000_000 * 10**18
        actual_balance = usdc.balanceOf(deployer)

        if actual_balance == expected_balance:
            print(f"Success! Balance verified: {actual_balance / 10**18} USDC")
        else:
            print(f"Warning: Balance mismatch. Found {actual_balance}")

        return usdc
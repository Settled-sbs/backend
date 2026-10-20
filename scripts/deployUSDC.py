from ape import accounts, project, networks


def main():
    with networks.parse_network_choice("avalanche:fuji"):
        # 1. Load your Fuji account
        # Replace 'my_fuji_acc' with your alias or use accounts.load()
        deployer = accounts.load("spv_admin")
        deployer.set_autosign(True, passphrase="heathens")  # Ensure this is secure in production!


        print(f"Deploying USDC from: {deployer.address}")
        usdc = project.MockUSDC.deploy(sender=deployer)

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
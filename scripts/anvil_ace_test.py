from ape import accounts, project, networks


def main():
    with networks.parse_network_choice("ethereum:local:foundry") as provider:
        assert provider.chain_id == 31337, (
            f"Wrong chain ID: {provider.chain_id}"
        )

        # Use the first disposable Anvil account.
        deployer = accounts.test_accounts[0]

        print(f"Chain ID: {provider.chain_id}")
        print(f"Deployer: {deployer.address}")

        # Deploy implementation and target fixture.
        implementation = project.ACEGuard.deploy(
            sender=deployer
        )
        vault = project.TestVault.deploy(
            sender=deployer
        )

        print(f"ACEGuard implementation: {implementation.address}")
        print(f"TestVault: {vault.address}")

        # Confirm the target fixture is deployed.
        assert len(provider.get_code(vault.address)) > 0

        print("Deployment checks passed.")
        print("No EIP-7702 delegation has been attempted yet.")


if __name__ == "__main__":
    main()


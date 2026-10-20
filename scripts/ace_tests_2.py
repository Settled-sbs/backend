from ape import accounts, project, networks


def main():
    with networks.parse_network_choice("robinhood:testnet") as provider:
        deployer = accounts.load("alt_user")
        deployer.set_autosign(True, passphrase="heathens")

        impl = project.ACEGuard.deploy(sender=deployer)

        print(f"EOA:        {deployer.address}")
        print(f"ACEGuard:   {impl.address}")
        print(f"Before:     {deployer.delegate}")

        receipt = deployer.set_delegate(
            impl,
            gas=1_000_000,
        )

        print(f"TX:         {receipt.txn_hash}")
        print(f"Ape delegate: {deployer.delegate}")

        code = provider.get_code(deployer.address)        
        print(f"EOA code: {code.hex()}")
        print(f"Expected: {'ef0100' + impl.address[2:].lower()}")

        assert code.lower() == bytes.fromhex(
            "ef0100" + impl.address[2:]
        ).lower(), "7702 DELEGATION FAILED"
        print("7702 DELEGATION SUCCESSFUL")

if __name__ == "__main__":
    main()
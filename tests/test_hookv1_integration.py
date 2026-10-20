import pytest
from eth_abi import encode

from ape import accounts, project, reverts


MAX_SPEND_PER_TX = 100
MAX_SPEND_TOTAL = 150
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@pytest.fixture
def owner():
    return accounts.test_accounts[0]


@pytest.fixture
def recipient():
    return accounts.test_accounts[2]


@pytest.fixture
def hook(owner):
    return project.HookV1.deploy(sender=owner)


@pytest.fixture
def token(owner):
    return project.MockUSDC.deploy(sender=owner)


@pytest.fixture
def account(owner, hook, token):
    mock = project.Mock7579Account.deploy(
        hook.address,
        sender=owner,
    )

    # HookV1 keys configuration by msg.sender, so installation
    # must be forwarded through the mock smart account.
    install_data = encode(
        ["address", "address", "uint256", "uint256", "address[4]"],
        [
            owner.address,
            token.address,
            MAX_SPEND_PER_TX,
            MAX_SPEND_TOTAL,
            [
                token.address,
                ZERO_ADDRESS,
                ZERO_ADDRESS,
                ZERO_ADDRESS,
            ],
        ],
    )

    mock.installHook(install_data, sender=owner)
    token.mint(mock.address, 1_000, sender=owner)

    return mock


def test_installation_records_mock_account(hook, account):
    assert hook.isInitialized(account.address) is True
    assert hook.isWhitelisted(account.address, account.address) is False


def test_allowed_transfer_records_spend(
    hook, account, token, recipient, owner
):
    tx = account.execute(
        token.address,
        0,
        token.transfer.encode_input(recipient.address, 40),
        sender=owner,
    )

    assert tx.status == 1
    assert token.balanceOf(recipient.address) == 40
    assert token.balanceOf(account.address) == 960

    config = hook.getConfig(account.address)
    assert config[6] == 40


def test_non_whitelisted_target_reverts(
    hook, account, owner, recipient
):
    other_token = project.MockUSDC.deploy(sender=owner)

    with reverts("target not whitelisted"):
        account.execute(
            other_token.address,
            0,
            other_token.transfer.encode_input(recipient.address, 1),
            sender=owner,
        )


def test_approval_selector_is_blocked(
    account, token, recipient, owner
):
    with reverts("allowance methods blocked"):
        account.execute(
            token.address,
            0,
            token.approve.encode_input(recipient.address, 10),
            sender=owner,
        )


def test_per_transaction_spend_limit_reverts_atomically(
    hook, account, token, recipient, owner
):
    with reverts("exceeds per-tx spending limit"):
        account.execute(
            token.address,
            0,
            token.transfer.encode_input(recipient.address, 101),
            sender=owner,
        )

    # The target transfer and hook accounting should both roll back.
    assert token.balanceOf(account.address) == 1_000
    assert token.balanceOf(recipient.address) == 0

    config = hook.getConfig(account.address)
    assert config[6] == 0


def test_cumulative_spend_limit_reverts(
    hook, account, token, recipient, owner
):
    # First spend: 80, within both limits.
    account.execute(
        token.address,
        0,
        token.transfer.encode_input(recipient.address, 80),
        sender=owner,
    )

    # Second spend: individually valid (70 <= 100), but cumulative
    # spend would become 150, which is allowed. This should succeed.
    account.execute(
        token.address,
        0,
        token.transfer.encode_input(recipient.address, 70),
        sender=owner,
    )

    assert hook.getConfig(account.address)[6] == 150

    # Any further positive spend exceeds the lifetime cap.
    with reverts("exceeds total spending limit"):
        account.execute(
            token.address,
            0,
            token.transfer.encode_input(recipient.address, 1),
            sender=owner,
        )

    assert hook.getConfig(account.address)[6] == 150
    assert token.balanceOf(account.address) == 850
    assert token.balanceOf(recipient.address) == 150

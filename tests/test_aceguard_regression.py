import pytest

from ape import accounts, chain, project, reverts


MAX_CALLS = 5
MAX_VALUE = 10**18
EPOCH_DURATION = 1_000_000


@pytest.fixture
def owner():
    return accounts.test_accounts[0]


@pytest.fixture
def attacker():
    return accounts.test_accounts[1]


@pytest.fixture
def vault(owner):
    return project.TestVault.deploy(sender=owner)


@pytest.fixture
def guard(owner, vault):
    instance = project.ACEGuard.deploy(sender=owner)

    instance.setup(
        owner.address,
        MAX_CALLS,
        MAX_VALUE,
        EPOCH_DURATION,
        sender=owner,
    )

    instance.setAllowedTarget(vault.address, True, sender=owner)

    safe_calldata = vault.harmlessAction.encode_input()
    instance.setAllowedSelector(safe_calldata[:4], True, sender=owner)

    return instance


def test_allowed_target_and_selector_execute(guard, vault, owner):
    calldata = vault.harmlessAction.encode_input()

    tx = guard.execute(
        vault.address,
        calldata,
        sender=owner,
    )

    assert tx.status == 1

    state = guard.epoch_states(owner.address, vault.address)
    assert state[1] == 1


def test_disallowed_selector_reverts(guard, vault, owner):
    # deposit() is deliberately not allowlisted.
    calldata = vault.deposit.encode_input()

    with reverts("Unauthorized Selector"):
        guard.execute(
            vault.address,
            calldata,
            sender=owner,
        )


def test_disallowed_target_reverts(guard, owner):
    other_vault = project.TestVault.deploy(sender=owner)
    calldata = other_vault.harmlessAction.encode_input()

    with reverts("Target not allowed"):
        guard.execute(
            other_vault.address,
            calldata,
            sender=owner,
        )


def test_sixth_call_in_same_epoch_reverts(guard, vault, owner):
    calldata = vault.harmlessAction.encode_input()

    # Mine each transaction normally. If execution crosses an epoch
    # boundary, restart this test with a larger epoch duration.
    for _ in range(MAX_CALLS):
        tx = guard.execute(
            vault.address,
            calldata,
            sender=owner,
        )
        assert tx.status == 1

    state = guard.epoch_states(owner.address, vault.address)
    assert state[1] == MAX_CALLS

    with reverts("ACE: Call limit"):
        guard.execute(
            vault.address,
            calldata,
            sender=owner,
        )


def test_call_counter_resets_in_next_epoch(guard, vault, owner):
    calldata = vault.harmlessAction.encode_input()

    for _ in range(MAX_CALLS):
        guard.execute(
            vault.address,
            calldata,
            sender=owner,
        )

    current_timestamp = chain.blocks.head.timestamp
    next_epoch_timestamp = (
        current_timestamp // EPOCH_DURATION + 1
    ) * EPOCH_DURATION

    # Advance the local test chain beyond the current epoch.
    chain.mine(timestamp=next_epoch_timestamp)

    tx = guard.execute(
        vault.address,
        calldata,
        sender=owner,
    )
    assert tx.status == 1

    state = guard.epoch_states(owner.address, vault.address)
    assert state[1] == 1


def test_non_owner_cannot_change_policy(guard, vault, attacker):
    calldata = vault.harmlessAction.encode_input()
    selector = calldata[:4]

    with reverts("Not owner"):
        guard.setAllowedTarget(
            vault.address,
            False,
            sender=attacker,
        )

    with reverts("Not owner"):
        guard.setAllowedSelector(
            selector,
            False,
            sender=attacker,
        )


def test_setup_rejects_second_initialization(guard, owner):
    with reverts("Already initialized"):
        guard.setup(
            owner.address,
            MAX_CALLS,
            MAX_VALUE,
            EPOCH_DURATION,
            sender=owner,
        )


def test_fresh_guard_can_be_initialized_by_first_caller(attacker):
    """
    SECURITY FINDING: documents current behavior, not desired behavior.

    This test passes only while setup() remains permissionless on a
    fresh guard. Replace it with a test expecting unauthorized setup
    to revert after initialization is secured.
    """
    fresh_guard = project.ACEGuard.deploy(sender=attacker)

    fresh_guard.setup(
        attacker.address,
        MAX_CALLS,
        MAX_VALUE,
        EPOCH_DURATION,
        sender=attacker,
    )

    assert fresh_guard.initialized() is True
    assert fresh_guard.owner() == attacker.address

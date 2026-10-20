# @version ^0.4.0

from ethereum.ercs import IERC20


struct Session:
    approved: bool
    max_amount: uint256      # Max this spender can spend from vault
    spent: uint256           # How much they've spent
    expires: uint256         # Timestamp

event SessionCreated:
    spender: indexed(address)
    amount: indexed(uint256)
    duration: indexed(uint256)

event Withdrawal:
    sender: indexed(address)
    destination: indexed(address)
    amount: indexed(uint256)

event SessionTerminated:
    _for: indexed(address)


sessions: public(HashMap[address, Session])
usdc: public(address)
owner: public(address)


@deploy
def __init__(_usdc: address):
    self.usdc = _usdc
    self.owner = msg.sender


@external
def balanceOfSession() -> uint256:
    return self.sessions[msg.sender].max_amount - self.sessions[msg.sender].spent

@external
def close_session():
    """Buyer can revoke anytime"""
    self.sessions[msg.sender].approved = False
    log SessionTerminated(msg.sender)

@external
@nonreentrant
def create_session(max_amount: uint256, duration_days: uint256):
    """
    Create/extend a session for msg.sender (the relayer).
    This authorizes them to spend up to max_amount from SnowGate vault.
    """
    # Only owner or admin can create sessions? Or anyone can self-authorize?
    # For now: anyone can create their own session (they're authorizing themselves to spend vault funds)
    # But actually, this should probably be restricted to approved relayers
    
    new_max: uint256 = max_amount
    new_spent: uint256 = 0
    
    # If extending existing session, preserve spent amount unless resetting
    current: Session = self.sessions[msg.sender]
    if current.approved and current.expires > block.timestamp:
        # Extending - keep spent amount, add new budget to remaining
        remaining: uint256 = current.max_amount - current.spent
        new_max = remaining + max_amount  # Add new budget to remaining
        new_spent = current.spent
    
    self.sessions[msg.sender] = Session({
        approved: True,
        max_amount: new_max,
        spent: new_spent,
        expires: block.timestamp + (duration_days * 86400)
    })
    
    log SessionCreated(msg.sender, new_max, duration_days)

    

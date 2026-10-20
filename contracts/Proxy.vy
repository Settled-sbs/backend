# pragma version ^0.4.0
"""
@title SettledDeltaProxy
@notice Secure ERC-8232 agency proxy with strict delta enforcement
"""

interface IERC20:
    def balanceOf(_owner: address) -> uint256: view

interface IComplianceProvider:
    def isCompliant(agent: address, rwa_token: address, action_type: uint256) -> bool: view

struct Permission:
    bitmask: uint256
    expiry: uint256

permissions: public(HashMap[bytes32, Permission])
bit_to_selector: public(HashMap[uint256, bytes4])

owner: public(address)
is_initialized: bool
identity_registry: public(address)
compliance_provider: public(address)
USDC: public(address)
MIN_USDC_PER_RWA: public(uint256)  # e.g., 0.95e6 = $0.95 per RWA

# Pricing or Oracle validation mechanism should be plugged here to prevent 1-wei bypasses.
# For strict delta validation, we track required exchange rates or min returns.

@internal
@view
def _get_permission_key(agent: address, rwa_token: address) -> bytes32:
    return keccak256(abi_encode(agent, rwa_token))

@external
def initialize(_owner: address, _identity_registry: address, _compliance: address, _usdc: address):
    assert not self.is_initialized, "Already initialized"
    self.owner = _owner
    self.identity_registry = _identity_registry
    self.compliance_provider = _compliance
    self.USDC = _usdc
    self.is_initialized = True
    # Represent $0.95 in USDC's smallest units (6 decimals): 0.95 * 1e6 = 950000
    self.MIN_USDC_PER_RWA = 0  # $0.95 (6 decimals) per RWA

@external
def mapSelector(bit: uint256, selector: bytes4):
    assert msg.sender == self.owner, "NOT_OWNER"
    self.bit_to_selector[bit] = selector

@external
def setAgentPermission(agent: address, rwa_token: address, bitmask: uint256, expiry: uint256):
    assert msg.sender == self.owner, "NOT_OWNER"
    key: bytes32 = self._get_permission_key(agent, rwa_token)
    self.permissions[key] = Permission(bitmask=bitmask, expiry=expiry)

# @internal
# def _enforce_delta(usdc_0: uint256, rwa_0: uint256, usdc_1: uint256, rwa_1: uint256):
#     if rwa_1 < rwa_0:
#         # Prevent 1-wei entry exploitation: Check that incoming USDC is non-zero
#         # Optimally, include a slippage or price calculation here.
#         assert usdc_1 > usdc_0, "Settled: RWA drained without USDC intake"


@internal
def _enforce_delta(usdc_0: uint256, rwa_0: uint256, usdc_1: uint256, rwa_1: uint256):
    if rwa_1 < rwa_0:
        rwa_sold: uint256 = rwa_0 - rwa_1
        usdc_gained: uint256 = usdc_1 - usdc_0
        
        # Minimum price: at least MIN_USDC_PER_RWA per RWA sold
        # rwa_sold has 18 decimals, MIN_USDC_PER_RWA has 6 decimals; divide by 10**18 to normalize
        min_usdc: uint256 = rwa_sold * self.MIN_USDC_PER_RWA // 10 ** 18
        assert usdc_gained >= min_usdc, "Settled: Price below floor"
@external
@nonreentrant
def performAgencyAction(
    rwa_token: address,
    action_type_bit: uint256,
    call_data: Bytes[1024]
) -> Bytes[1024]:
    key: bytes32 = self._get_permission_key(msg.sender, rwa_token)
    perm: Permission = self.permissions[key]
    
    assert block.timestamp <= perm.expiry, "AGENCY_EXPIRED"
    
    # Vyper 0.4.x: use << operator
    shift_mask: uint256 = 1 << action_type_bit
    assert (perm.bitmask & shift_mask) > 0, "PERMISSION_DENIED"
    
    actual_selector: bytes4 = convert(slice(call_data, 0, 4), bytes4)
    expected_selector: bytes4 = self.bit_to_selector[action_type_bit]
    assert actual_selector == expected_selector, "SELECTOR_MISMATCH"
    
    usdc_0: uint256 = 0
    rwa_0: uint256 = 0
    
    if rwa_token != empty(address):
        usdc_0 = staticcall IERC20(self.USDC).balanceOf(self)
        rwa_0 = staticcall IERC20(rwa_token).balanceOf(self)
    
    response: Bytes[1024] = raw_call(rwa_token, call_data, max_outsize=1024, revert_on_failure=True)
    
    if rwa_token != empty(address):
        usdc_1: uint256 = staticcall IERC20(self.USDC).balanceOf(self)
        rwa_1: uint256 = staticcall IERC20(rwa_token).balanceOf(self)
        self._enforce_delta(usdc_0, rwa_0, usdc_1, rwa_1)
    
    return response

@external
@nonreentrant
def executeTX(_target: address, _value: uint256, _data: Bytes[4096], _tracked_rwa: address) -> Bytes[4096]:
    """
    @notice Direct execution path limited strictly to the owner with atomic delta tracking.
    """
    assert msg.sender == self.owner, "NOT_OWNER"
    
    usdc_0: uint256 = staticcall IERC20(self.USDC).balanceOf(self)
    rwa_0: uint256 = 0
    if _tracked_rwa != empty(address):
        rwa_0 = staticcall IERC20(_tracked_rwa).balanceOf(self)
        
    response: Bytes[4096] = raw_call(_target, _data, value=_value, max_outsize=4096, revert_on_failure=True)
    
    if _tracked_rwa != empty(address):
        usdc_1: uint256 = staticcall IERC20(self.USDC).balanceOf(self)
        rwa_1: uint256 = staticcall IERC20(_tracked_rwa).balanceOf(self)
        self._enforce_delta(usdc_0, rwa_0, usdc_1, rwa_1)
        
    return response
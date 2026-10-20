# pragma version ^0.4.3

master_proxy: public(address)
get_proxy_by_owner: public(HashMap[address, address])
get_owner_by_proxy: public(HashMap[address, address])
ERC8004_address: public(address)
USDC_address: public(address)

event ProxyDeployed:
    owner: indexed(address)
    proxy_address: address

@deploy
def __init__(_master_proxy: address, _erc8004: address, _usdc: address):
    self.master_proxy = _master_proxy
    self.ERC8004_address = _erc8004
    self.USDC_address = _usdc

@external
def getMyProxy() -> address:
    return self.get_proxy_by_owner[msg.sender]

@external
def getProxyOwner(proxy: address) -> address:
    return self.get_owner_by_proxy[proxy]

@external
def deploy_settled_proxy() -> address:
    assert self.get_proxy_by_owner[msg.sender] == empty(address), "Proxy already exists"

    # Deploy standard EIP-1167 Minimal Proxy pointing to master implementation
    new_proxy: address = create_minimal_proxy_to(self.master_proxy)

    # Standard Vyper 0.4.0 initialization 
    initialize_data: Bytes[160] = concat(
        method_id("initialize(address,address,address,address)"),
        convert(msg.sender, bytes32),            # _owner
        convert(self.ERC8004_address, bytes32),  # _identity_registry
        convert(empty(address), bytes32),        # _compliance (or designated provider)
        convert(self.USDC_address, bytes32)      # _usdc
    )
    # Force revert on initialization failure to expose inner errors
    raw_call(new_proxy, initialize_data, revert_on_failure=True)
    
    self.get_proxy_by_owner[msg.sender] = new_proxy
    self.get_owner_by_proxy[new_proxy] = msg.sender

    log ProxyDeployed(owner=msg.sender, proxy_address=new_proxy)
    return new_proxy
import requests
from ape import contracts
from fastapi import (
    APIRouter, FastAPI, HTTPException
    , Request, BackgroundTasks
)
from pydantic import BaseModel
from eth_abi import encode
from eth_utils import keccak
from app.core.schemas import AgentRequest
from app.core.schemas import *
from app.core.settings import settings
from fastapi.responses import StreamingResponse

router = APIRouter()

# Target liquidity/asset pool your AI wants to interact with
RWA_ADDRESS = "0xD4432C0374C4AB4e300d7BA8CE6AB4e62Ad1f190"

# Contract addresses (Fuji)
FILTER = "0xbe0B1E44555f7cf3526bBa0147B9F38Ea1B96a7a"  # Settled Guard filter contract that users interact with
USDC = settings.usdc_address



def build_execute_calldata(target: str, value: int, inner_calldata: bytes) -> str:
    """
    Encode: execute(address target, uint256 value, bytes data)
    Selector: keccak256("execute(address,uint256,bytes)")[:4]
    """
    selector = keccak(text="execute(address,uint256,bytes)")[:4]
    encoded = encode(
        ['address', 'uint256', 'bytes'],
        [target, value, inner_calldata]
    )
    return '0x' + selector.hex() + encoded.hex()

def build_swap_calldata(token_in: str, token_out: str, amount: int) -> bytes:
    """
    Example: encode a swap on VendorShop
    Replace with your actual VendorShop interface
    """
    # Example: swap(address tokenIn, address tokenOut, uint256 amount)
    selector = keccak(text="swap(address,address,uint256)")[:4]
    encoded = encode(
        ['address', 'address', 'uint256'],
        [token_in, token_out, amount]
    )
    return selector + encoded

@router.post("/rebalance")
def rebalance(req: AgentRequest):
    # AI decides: sell 100 RWA, buy USDC
    rwa_amount = 100 * 10**18  # 100 RWA tokens
    
    # Build the inner call to VendorShop
    inner_calldata = build_swap_calldata(
        token_in=RWA_ADDRESS,  # RWA
        token_out=USDC,                # USDC
        amount=rwa_amount
    )
    
    # Wrap it through the filter
    filter_calldata = build_execute_calldata(
        target=FILTER,
        value=0,
        inner_calldata=inner_calldata
    )
    
    return {
        "action_type": "rebalance",
        "description": f"Sell {rwa_amount / 1e18} RWA for USDC",
        "target": FILTER,           # User calls filter
        "calldata": filter_calldata, # execute(VendorShop, 0, swap(RWA, USDC, amount))
        "value": 0
    }

@router.post("/rebase")
def rebase(req: AgentRequest):
    # Example: claim yield or check rebasing
    inner_calldata = keccak(text="checkRebase()")[:4]
    
    filter_calldata = build_execute_calldata(
        target=FILTER,
        value=0,
        inner_calldata=inner_calldata
    )
    
    return {
        "action_type": "rebase",
        "description": "Trigger rebase check",
        "target": FILTER,
        "calldata": filter_calldata,
        "value": 0
    }


@router.post("/propose-action")
def propose_action(request: ExecutionRequest):
    try:
        # 1. Use Ape to load contract layout and encode parameters
        contract = contracts.from_address(RWA_ADDRESS)
        encoded_calldata = contract.executeStrategy.encode_input(1000) # Sample variables
        
        # 2. Package instructions and the frontend signature for the Node.js relay
        relay_payload = {
            "targetAddress": RWA_ADDRESS,
            "callData": encoded_calldata,
            "userOpAuthorization": request.user_auth_payload
        }
        
        # 3. Relay out to local port 3000
        response = requests.post("http://localhost:3000/relay/execute", json=relay_payload).json()
        
        if not response.get("success"):
            raise HTTPException(status_code=400, detail=response.get("error"))
            
        return {"status": "Success", "txHash": response["txHash"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/health")
def health():
    return {"status": "ok"}
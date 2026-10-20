from pydantic import BaseModel
from typing import Optional

class PurchaseRequest(BaseModel):
    shop: str
    product_id: int
    buyer_agent_id: int
    price: str

class ShopAddress(BaseModel):
    address: str

class UserPrompt(BaseModel):
    prompt: str

class BuyRequest(BaseModel):
    prompt: str
    userAddress: str

class PurchaseAction(BaseModel):
    action: str
    product: str
    quantity: Optional[int] = 1

class ExecutionRequest(BaseModel):
    user_auth_payload: dict  # Captures the cryptographic signature from Privy

class AgentRequest(BaseModel):
    wallet: str
    timestamp: int
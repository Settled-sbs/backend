from fastapi import (
    APIRouter, FastAPI, HTTPException
    , Request, BackgroundTasks
)
from app.core.schemas import *
from app.core.settings import settings

router = APIRouter()




@router.get("/login")
async def root(request: Request):
    return {
        "request": request, 
        "status": "SnowGate API"
    }


@router.post("/monitor")
async def start_monitoring(data: ShopAddress):
    """Start monitoring a shop for ProductDelivered events"""
    shop_addr = data.address.lower()
    
    # Cancel existing if running
    
    return {
        "status": "started",
        "shop": shop_addr,
        "message": "Delivery monitoring started"
    }

@router.delete("/monitor/{shop_addr}")
async def stop_monitoring(shop_addr: str):
    """Stop monitoring a specific shop"""
    shop_addr = shop_addr.lower()
    
    raise HTTPException(status_code=404, detail="Monitor not found")



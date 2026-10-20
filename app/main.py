from fastapi import (
    APIRouter, FastAPI, HTTPException
    , Request, BackgroundTasks
)
from app.core.settings import settings
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.routes import (
    authenticate,
    agent
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup


    yield
    
    # Shutdown

app = FastAPI(title="SnowGate API", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authenticate.router, prefix="/auth")
app.include_router(agent.router, prefix="/agent")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
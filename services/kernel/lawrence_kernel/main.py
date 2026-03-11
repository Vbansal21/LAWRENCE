from fastapi import FastAPI

from lawrence_kernel.routers import router

app = FastAPI(title="LAWRENCE Kernel", version="0.1.0")
app.include_router(router)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import appointments, chat, clients, providers, rooms

# Initialize
app = FastAPI()

app.include_router(providers.router)
app.include_router(chat.router)
app.include_router(rooms.router)
app.include_router(clients.router)
app.include_router(appointments.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "Booking API"}

@app.get("/health")
def health():
    return {"status": "healthy"}

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       
    allow_credentials=True,
    allow_methods=["*"],         
    allow_headers=["*"],         
)
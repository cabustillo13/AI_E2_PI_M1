from fastapi import FastAPI

from ticketflow.api.routes import router


app = FastAPI(
    title="TicketFlow",
    version="1.0.0",
)

app.include_router(router)
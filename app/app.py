from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/test")
def test():
    return {"msg": "test ok"}

@app.post("/webhook/landbot")
def webhook(payload: dict, x_api_key: str = None):
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

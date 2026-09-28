from fastapi import FastAPI

app = FastAPI(title="SME Energy Advisor")


@app.get("/health")
def health():
    return {"status": "ok"}
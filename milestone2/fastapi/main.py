import fastapi

app = fastapi.FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def hello():
    return {"message": "Welcome to mlops fastapi!"}


@app.get("/predict")
def predict():
    # Dummy prediction logic
    return {"prediction": "This is a dummy prediction."}


def main():
    print("Hello from mlops!")


if __name__ == "__main__":
    main()

import fastapi
from pydantic import BaseModel

app = fastapi.FastAPI()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def hello() -> dict:
    return {"message": "Welcome to mlops fastapi!"}


class PredictRequest(BaseModel):
    # Define your input data structure here
    data: str


class PredictResponse(BaseModel):
    # Define your output data structure here
    prediction: str


@app.get("/predict")
def predict(inputdata: PredictRequest) -> PredictResponse:
    # Dummy prediction logic
    prediction = f"Predicted value for input: {inputdata.data}"
    return PredictResponse(prediction=prediction)


def main() -> None:
    print("Hello from mlops!")


if __name__ == "__main__":
    main()

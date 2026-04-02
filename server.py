import fastapi
from pydantic import BaseModel

app = fastapi.FastAPI()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def hello() -> dict:
    return {"message": "Welcome to mlops fastapi!"}


@app.get("/usfca")
def usfca() -> str:
    print("someone requested the usfca endpoint")
    return "something"


@app.post("/add_query_parameters")
def addWithQueryParameters(num1: int, num2: int) -> dict:
    result = num1 + num2
    return {"result": result}


# add with body parameters
@app.post("/add_body_parameters")
def addWithBodyParameters(request: dict) -> dict:
    num1 = int(request.get("num1"))
    num2 = int(request.get("num2"))

    b0 = 27
    b1 = 256
    b2 = 339
    prediction = b0 + b1 * num1 + b2 * num2

    return {"result": prediction}


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

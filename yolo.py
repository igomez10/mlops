import torch
from transformers import pipeline

detector = pipeline(
    task="object-detection",
    model="hustvl/yolos-base",
    dtype=torch.float16,
    device=0
)

res = detector("https://huggingface.co/datasets/Narsil/image_dummy/raw/main/parrots.png")
print(res)

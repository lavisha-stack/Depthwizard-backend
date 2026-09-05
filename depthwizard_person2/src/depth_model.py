"""Select the compute device and load a pretrained model."""

from dataclasses import dataclass

from config import MODEL_CONFIGS


@dataclass
class LoadedDepthModel:
    model: object
    processor: object
    device: object
    key: str
    info: dict


def select_device():
    """Prefer an NVIDIA CUDA GPU, while keeping CPU fully supported."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is missing. Run: pip install -r requirements.txt") from exc
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_depth_model(model_key: str) -> LoadedDepthModel:
    """Download/cache and load the requested pretrained depth model."""
    if model_key not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model '{model_key}'. Choices: {', '.join(MODEL_CONFIGS)}")
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as exc:
        raise RuntimeError("Transformers is missing. Run: pip install -r requirements.txt") from exc

    device = select_device()
    if device.type == "cuda":
        # Ampere and newer NVIDIA hardware benefits from TF32 for the float32
        # operations that remain outside autocast.
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    info = MODEL_CONFIGS[model_key]
    try:
        processor = AutoImageProcessor.from_pretrained(info["checkpoint"])
        model = AutoModelForDepthEstimation.from_pretrained(info["checkpoint"])
    except Exception as exc:
        raise RuntimeError(
            f"Could not load pretrained weights '{info['checkpoint']}'. Check your internet "
            "connection/disk space, or retry after the files are cached. You can also pass "
            "--model midas."
        ) from exc
    model.to(device)
    model.eval()
    return LoadedDepthModel(model, processor, device, model_key, info)

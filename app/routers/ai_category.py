"""
AI image category prediction router

Classifies an uploaded image into one of the fixed class labels and returns
the predicted label along with probabilities for all classes.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from typing import List, Dict
import os
import io
import json
from datetime import datetime
import logging

from app.schemas.ai_outputs import AICategoryPredictionResponse

router = APIRouter(prefix="/ai", tags=["AI Category"])
logger = logging.getLogger("router.ai_category")

# Fixed class labels per request
CLASS_LABELS: List[str] = [
    'Battery', 'Keyboard', 'Microwave', 'Mobile', 'Mouse',
    'PCB', 'Player', 'Printer', 'Television', 'Washing Machine'
]

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "ai_category_memories.json")


def _ensure_memory_file():
    try:
        dirpath = os.path.dirname(MEMORY_FILE)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w") as f:
                json.dump([], f)
    except Exception:
        pass


def _load_memories():
    _ensure_memory_file()
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_memory(record: dict):
    # Try langgraph first if present
    try:
        from langgraph import LangGraph, MemoryRecord  # type: ignore
        lg = LangGraph(store_path=os.path.join(os.path.dirname(__file__), "..", "langgraph_store"))
        memory = MemoryRecord(content=json.dumps(record))
        lg.add_memory(memory)
        return True
    except Exception:
        try:
            _ensure_memory_file()
            memories = _load_memories()
            memories.append(record)
            with open(MEMORY_FILE, "w") as f:
                json.dump(memories, f, indent=2)
            return True
        except Exception:
            return False


@router.get("/category/labels")
async def get_labels():
    return {"labels": CLASS_LABELS}


def _build_prompt_for_probs() -> str:
    # Ask the model to strictly output JSON with probabilities for all labels
    labels_str = ", ".join([f'"{lbl}"' for lbl in CLASS_LABELS])
    return (
        "You are an image classification assistant.\n\n"
        "Task: Given the input image, classify it into exactly one of the following labels and also provide a probability distribution across all labels.\n\n"
        f"Labels: [{labels_str}]\n\n"
        "Output STRICT JSON only with keys: predicted_label (string), probabilities (object mapping each label to a number between 0 and 1 that sums ~1).\n"
        "No explanations."
    )


def _empty_distribution() -> Dict[str, float]:
    n = len(CLASS_LABELS)
    return {lbl: (1.0 / n) for lbl in CLASS_LABELS}


@router.post("/category/predict", response_model=AICategoryPredictionResponse)
async def predict_category(image: UploadFile = File(...)):
    # Validate content type
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a valid image file")

    # Read image bytes
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise ValueError("Empty image")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to read image: {e}")

    # Ensure API key
    google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_CREDENTIALS")
    if not google_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GOOGLE_API_KEY not configured")

    # Try Google Gemini multimodal
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        logger.exception("google.generativeai not installed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="google-generativeai not installed")

    try:
        genai.configure(api_key=google_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")  # faster for classification

        prompt = _build_prompt_for_probs()
        # Convert bytes to the image part expected by the SDK
        img_part = {"mime_type": image.content_type, "data": image_bytes}
        generation = model.generate_content([prompt, img_part])

        resp_text = None
        if hasattr(generation, "text") and generation.text:
            resp_text = generation.text
        elif hasattr(generation, "candidates") and generation.candidates:
            parts = []
            for cand in generation.candidates:
                try:
                    for part in cand.content.parts:
                        if hasattr(part, "text") and part.text:
                            parts.append(part.text)
                except Exception:
                    continue
            resp_text = "\n".join(parts) if parts else None
        if not resp_text:
            raise ValueError("Empty response from Gemini")
    except Exception as e:
        logger.exception("Gemini call failed: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gemini call failed: {e}")

    # Parse strict JSON
    try:
        parsed = json.loads(resp_text)
    except Exception:
        try:
            start = resp_text.find("{")
            end = resp_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(resp_text[start:end+1])
            else:
                raise ValueError("No valid JSON found in model response")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Invalid model response: {e}")

    # Normalize and validate probabilities
    probs: Dict[str, float] = _empty_distribution()
    try:
        raw_probs = parsed.get("probabilities", {}) or {}
        for lbl in CLASS_LABELS:
            val = raw_probs.get(lbl, 0.0)
            try:
                f = float(val)
            except Exception:
                f = 0.0
            if f < 0:
                f = 0.0
            probs[lbl] = f
        # Normalize to sum to 1.0 if all zeros or not summing
        s = sum(probs.values())
        if s <= 0:
            probs = _empty_distribution()
        else:
            probs = {k: (v / s) for k, v in probs.items()}
        predicted_label = str(parsed.get("predicted_label", "")).strip()
        if predicted_label not in CLASS_LABELS:
            # choose argmax
            predicted_label = max(probs.items(), key=lambda kv: kv[1])[0]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Malformed JSON from model: {e}")

    # Save memory (best-effort)
    try:
        _save_memory({
            "filename": image.filename,
            "content_type": image.content_type,
            "predicted_label": predicted_label,
            "probabilities": probs,
            "created_at": datetime.utcnow().isoformat()
        })
    except Exception:
        logger.exception("Failed to save category memory")

    return AICategoryPredictionResponse(predicted_label=predicted_label, probabilities=probs)


@router.get("/category/debug")
async def category_debug():
    info = {
        "google_api_key_present": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_CREDENTIALS")),
        "google_generative_client": False,
        "google_generative_version": None,
        "langgraph": False,
        "langgraph_version": None,
        "labels": CLASS_LABELS,
    }
    try:
        import google.generativeai as _genai  # type: ignore
        info["google_generative_client"] = True
        try:
            from importlib.metadata import version as _ver  # type: ignore
            info["google_generative_version"] = _ver("google-generativeai")
        except Exception:
            pass
    except Exception:
        pass
    try:
        from importlib.metadata import version as _ver
        from langgraph import LangGraph  # type: ignore
        info["langgraph"] = True
        info["langgraph_version"] = _ver("langgraph")
    except Exception:
        pass
    return info

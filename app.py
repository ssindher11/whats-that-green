import os
import io
import json
import base64
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("whats-that-green")

# Initialize Flask app
app = Flask(__name__)
# Maximum allowed payload: 16 MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# Pydantic Schema for Structured Output
class CareTips(BaseModel):
    water: str = Field(description="Detailed yet concise watering requirements and schedule")
    light: str = Field(description="Sunlight conditions (direct sunlight, bright indirect, shade, etc.)")
    soil: str = Field(description="Recommended soil composition, drainage needs, and potting medium")

class PlantIdentification(BaseModel):
    is_plant: bool = Field(description="True if the image contains a plant, leaf, flower, succulent, fungi, or botanical specimen; False otherwise")
    plant_name: str = Field(description="Common name of the plant or subject")
    scientific_name: str = Field(description="Botanical binomial Latin name, or 'N/A' if not a plant")
    confidence: str = Field(description="Estimated confidence percentage and certainty level (e.g., '96% - High', '75% - Moderate')")
    description: str = Field(description="A brief, engaging 2-sentence summary of the plant's unique characteristics, origins, or habitat")
    care_tips: CareTips

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_genai_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")
    from google import genai
    return genai.Client(api_key=api_key)

def process_image_bytes(raw_bytes: bytes) -> tuple[bytes, str]:
    """Validate and normalize image using Pillow."""
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Convert to RGB if necessary (e.g. RGBA, CMYK, Palette)
            if img.mode in ("RGBA", "LA", "P"):
                # Handle alpha channel with clean white background
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Downscale if excessively large to ensure fast Gemini processing
            max_dimension = 2048
            if max(img.width, img.height) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=90)
            return output.getvalue(), "image/jpeg"
    except Exception as exc:
        logger.error(f"Image processing failed: {exc}")
        raise ValueError(f"Invalid or corrupted image file: {str(exc)}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "model": MODEL_NAME,
        "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))
    })

@app.route("/identify", methods=["POST"])
def identify():
    if not os.getenv("GEMINI_API_KEY"):
        return jsonify({
            "success": False,
            "error": "Gemini API key is not configured. Please set GEMINI_API_KEY in your .env file."
        }), 500

    image_bytes = None
    mime_type = "image/jpeg"

    # 1. Check for standard multipart file upload
    if "image" in request.files:
        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected."}), 400
        if not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "error": f"Unsupported file type. Please upload a {', '.join(sorted(ALLOWED_EXTENSIONS))} image."
            }), 400
        raw_bytes = file.read()
        try:
            image_bytes, mime_type = process_image_bytes(raw_bytes)
        except ValueError as err:
            return jsonify({"success": False, "error": str(err)}), 400

    # 2. Check for base64 encoded image (common for live camera snapshot)
    elif request.is_json and "image_data" in request.json:
        data_uri = request.json.get("image_data", "")
        if not data_uri:
            return jsonify({"success": False, "error": "No image data provided."}), 400
        try:
            # Handle Data URL format: "data:image/jpeg;base64,...."
            if "," in data_uri:
                _, base64_data = data_uri.split(",", 1)
            else:
                base64_data = data_uri
            raw_bytes = base64.b64decode(base64_data)
            image_bytes, mime_type = process_image_bytes(raw_bytes)
        except Exception as exc:
            return jsonify({"success": False, "error": f"Invalid base64 image data: {str(exc)}"}), 400
    else:
        return jsonify({
            "success": False,
            "error": "No image provided. Please upload an image file or take a photo."
        }), 400

    try:
        from google.genai import types
        client = get_genai_client()

        # Build multimodal prompt
        system_instruction = (
            "You are a world-class expert botanist, horticulturist, and plant taxonomist. "
            "Analyze the submitted image with meticulous botanical precision. "
            "Examine leaf morphology, venation, leaf margins, stem structure, flower anatomy, "
            "coloration, and texture to identify the plant species.\n\n"
            "If the image clearly does not depict a plant, flower, tree, succulent, or fungi, "
            "set 'is_plant' to false, provide the likely subject name in 'plant_name', set 'scientific_name' to 'N/A', "
            "give a polite 2-sentence explanation in 'description', and provide 'N/A' for care tips.\n\n"
            "If it is a plant, provide the accurate common name, precise botanical Latin name, your confidence level, "
            "an engaging 2-sentence summary, and 3 targeted care guidelines for watering, lighting, and soil."
        )

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        user_prompt = (
            "Please examine this image carefully. Identify what plant it is, "
            "estimate your confidence level, write a brief 2-sentence botanical description, "
            "and provide essential care tips for water, light, and soil."
        )

        # Configure structured schema and reasoning budget
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=PlantIdentification,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
            temperature=0.2
        )

        candidate_models = [MODEL_NAME]
        if "gemini-2.5-flash" not in candidate_models:
            candidate_models.append("gemini-2.5-flash")

        response = None
        last_error = None

        for model_candidate in candidate_models:
            try:
                logger.info(f"Querying Gemini model '{model_candidate}' for plant identification...")
                response = client.models.generate_content(
                    model=model_candidate,
                    contents=[image_part, user_prompt],
                    config=config
                )
                if response and response.text:
                    break
            except Exception as candidate_err:
                logger.warning(f"Model '{model_candidate}' failed: {candidate_err}")
                last_error = candidate_err
                continue

        if not response or not response.text:
            raise last_error or RuntimeError("No response returned from Gemini API.")

        raw_response_text = response.text or ""
        logger.info(f"Received Gemini response: {raw_response_text[:120]}...")

        # Parse JSON response
        try:
            result_data = json.loads(raw_response_text)
        except json.JSONDecodeError:
            # Clean markdown codeblocks if present
            cleaned_text = raw_response_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.split("\n", 1)[-1]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text.rsplit("\n", 1)[0]
            result_data = json.loads(cleaned_text.strip())

        return jsonify({
            "success": True,
            "data": result_data
        })

    except Exception as exc:
        logger.exception("Error during plant identification")
        return jsonify({
            "success": False,
            "error": f"Botany analysis failed: {str(exc)}"
        }), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    debug_mode = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting 'What\'s that Green Thing' server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)

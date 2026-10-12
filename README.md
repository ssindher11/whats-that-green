# 🌿 What's that Green Thing

A modern, nature-inspired single-page web application that identifies plants from user-submitted images or live webcam snapshots using **Google Gemini 3.8 Flash** with high-effort reasoning and structured output via the official `google-genai` SDK.

---

## ✨ Features

- **Dual Input Methods:**
  - 📁 **File Upload & Drag-and-Drop:** Seamlessly drop or browse image files (`.jpg`, `.png`, `.webp`).
  - 📷 **Live Webcam Capture:** View a live camera stream with specimen viewfinder framing, switch between front/back lenses, and snap high-resolution photos directly in your browser.
- **Expert Botanical Reasoning:**
  - Powered by `gemini-3.8-flash` with thinking budget reasoning.
  - Returns structured botanical data:
    - **Common Name**
    - **Scientific Botanical Name** (Latin binomial)
    - **Confidence Score**
    - **Engaging 2-Sentence Overview**
    - **3 Targeted Care Tips**: Water 💧, Sunlight ☀️, and Soil 🌱
- **Nature-Inspired UI / UX:**
  - Sage green and earthy aesthetic built with Tailwind CSS.
  - Interactive loading state with a smooth spinner and a rotating botanical text ticker (*"Consulting the forest spirits...", "Analyzing leaf venation...", etc.*).
  - Elegant results presentation card with copy-to-clipboard functionality and side-by-side specimen comparison.

---

## 🚀 Quick Start

### 1. Activate Environment & Install Dependencies

```bash
# If using the already configured virtual environment:
source .venv/bin/activate

# Or install dependencies directly:
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Your `.env` file should contain your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
PORT=5001
```

*(See `.env.example` for details)*

### 3. Run the Application

```bash
python app.py
```

Open your browser at:
👉 **[http://localhost:5001](http://localhost:5001)**

---

## 📁 Project Structure

```
whats-that-green/
├── app.py                 # Flask server with GenAI SDK, image preprocessing & /identify API
├── requirements.txt       # Dependencies (flask, google-genai, python-dotenv, pillow)
├── .env                   # Environment file containing GEMINI_API_KEY
├── .env.example           # Example environment template
├── templates/
│   └── index.html         # Single-page UI with Tailwind CDN, live camera & results card
└── README.md              # Project documentation
```

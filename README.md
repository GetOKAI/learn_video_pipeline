## 🎬 AI Video Generation Pipeline (Gemini 2.5)

This project automates the generation of **enhanced prompts**, **actor dialogue scripts**, and **faceless narration scripts** for video content using Google’s **Gemini 2.5-Flash** model.
The pipeline runs automatically upon execution — no manual input or browser interaction required.

---

### ⚙️ Setup Instructions

#### 1️⃣ Clone Repository

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

#### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# or
source venv/bin/activate   # Mac/Linux
```

#### 3️⃣ Install Dependencies

```bash
pip install --no-cache-dir -r requirements.txt
```

#### 4️⃣ Configure Environment

Create a `.env` file with your Gemini API key:

```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

#### 5️⃣ Add Input File

Ensure the file `Video_generation_prompts_filtered.json` is present in the same directory as `app.py`.
Example structure:

```json
[
  {
    "Video Title": "How to open a bank account",
    "Prompts used for original video": "Create a short script..."
  }
]
```

---

### ▶️ Run the Pipeline

```bash
python app.py
```

The pipeline will:

1. Load input prompts
2. Generate enhanced, actor, and faceless scripts via Gemini
3. Save outputs as:

   * `enhanced_prompts.json`
   * `transcripts_actor.json`
   * `transcripts_faceless.json`

---

### ☁️ Deployment (GCP Cloud Run)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8080
CMD ["python", "app.py"]
```

Deploy using:

```bash
gcloud run deploy ai-video-pipeline \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

### 📁 Output Overview

| File                        | Description                  |
| --------------------------- | ---------------------------- |
| `enhanced_prompts.json`     | Refined and creative prompts |
| `transcripts_actor.json`    | Two-person dialogue scripts  |
| `transcripts_faceless.json` | Single-narration scripts     |

---

**Tech Stack:** Python · Flask · Google Gemini API · GCP Cloud Run
**Author:** Vraj Patel

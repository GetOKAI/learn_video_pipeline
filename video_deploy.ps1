# ==============================
# Deploy Profile Extraction Service (Force Rebuild + Redeploy)
#CHANGE FOR VIDEO PIPELINE
# ==============================

Write-Host ">>> Setting variables..."

$PROJECT="ok-ai-otp"
$REGION="us-central1"
$REPO="okai-automation"
$SERVICE="automate-profile-extraction-service"
$TAG="v1"
$IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/profile-extraction-service:$TAG"

Write-Host ">>> Project: $PROJECT"
Write-Host ">>> Region: $REGION"
Write-Host ">>> Artifact Registry Path: $IMAGE"

# -------------------------------
# Step 1: Configure Docker auth
# -------------------------------
Write-Host ">>> Configuring Docker authentication..."
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

# -------------------------------
# Step 2: Force rebuild Docker image (no cache)
# -------------------------------
Write-Host ">>> Building Docker image locally (no cache)..."
docker build --no-cache -t $IMAGE .

# -------------------------------
# Step 3: Push Docker image to Artifact Registry
# -------------------------------
Write-Host ">>> Pushing image to Artifact Registry..."
docker push $IMAGE

# -------------------------------
# Step 4: Deploy to Cloud Run
# -------------------------------
Write-Host ">>> Deploying to Cloud Run..."
gcloud run deploy $SERVICE `
  --image=$IMAGE `
  --region=$REGION `
  --platform=managed `
  --allow-unauthenticated `
  --port=8080 `
  --set-env-vars "SUPABASE_URL=https://mbgpjhlvttvqxxlvxijp.supabase.co" `
  --set-env-vars "SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1iZ3BqaGx2dHR2cXh4bHZ4aWpwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTgwNzk4MywiZXhwIjoyMDcxMzgzOTgzfQ.IjXyWEHQvvYOEF8i4eJ6XctpMLQYKZHvmbGHvtprajY" `
  --set-env-vars "VAPI_API_KEY=bf7ae614-0e15-4cb9-bae0-571b6e1c9899" `
  --set-env-vars "ASSISTANT_ID=8a6b133b-bc29-461d-85a4-078c724cb7a6" `
  --set-env-vars "VAPI_TRANSCRIBE_URL=https://api.vapi.ai/transcriptions" `
  --set-env-vars "WEBHOOK_SECRET=supersecret123"

Write-Host ">>> Deployment finished!"
Write-Host ">>> Run this to check your service URL again if you missed it:"
Write-Host ">>> gcloud run services describe $SERVICE --region $REGION --format='value(status.url)'"
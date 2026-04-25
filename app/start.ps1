$env:JWT_SECRET_KEY="ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8="
$env:JWT_ACCESS_TOKEN_EXPIRE_HOURS="24"
$env:JWT_REFRESH_TOKEN_EXPIRE_DAYS="7"
$env:LANDBOT_SECRET_TOKEN="seu_token_landbot_secreto_123"
$env:DATABASE_URL="sqlite:///./test.db"
python -m uvicorn main:app --reload
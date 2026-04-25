import os
import pytest

os.environ["JWT_SECRET_KEY"] = "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8="
os.environ["JWT_ACCESS_TOKEN_EXPIRE_HOURS"] = "24"
os.environ["JWT_REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["LANDBOT_SECRET_TOKEN"] = "seu_token_landbot_secreto_123"

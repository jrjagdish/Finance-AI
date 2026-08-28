import logging

import inngest
from dotenv import load_dotenv

# The Inngest SDK reads INNGEST_DEV / INNGEST_EVENT_KEY / INNGEST_SIGNING_KEY straight
# from process env vars (not from app.core.config.Settings), so .env must be loaded into
# os.environ here — pydantic-settings' env_file loading only fills Settings' own fields.
load_dotenv()

# In local dev, set INNGEST_DEV=1 so the SDK targets the local Inngest Dev Server
# instead of Inngest Cloud. In production (e.g. Vercel), set INNGEST_EVENT_KEY and
# INNGEST_SIGNING_KEY — the SDK reads both directly from the environment.
inngest_client = inngest.Inngest(
    app_id="finance-ai",
    logger=logging.getLogger("uvicorn"),
)

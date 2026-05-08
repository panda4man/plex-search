import os

# Must be set before any app imports so get_settings() can load without a real .env
os.environ.setdefault("PLEX_SERVER_URL", "http://plex-test:32400")
os.environ.setdefault("PLEX_CLIENT_ID", "test-client-id-fixed")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-min-32-chars!!")
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama-test:11434")
os.environ.setdefault("FRONTEND_URL", "http://localhost-test")
os.environ.setdefault("PLEX_APP_NAME", "PlexSearchTest")

import os

# Must be set before `compass.main` is imported (it builds the app at import time).
os.environ.setdefault("COMPASS_PASSWORD", "test-password")
os.environ.setdefault("COMPASS_SECRET_KEY", "test-secret-key")

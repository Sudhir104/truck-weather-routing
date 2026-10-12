import os
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-key")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["corsheaders", "routing"]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware"]
ROOT_URLCONF = "trucksafe.urls"
CORS_ALLOW_ALL_ORIGINS = True
USE_TZ = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

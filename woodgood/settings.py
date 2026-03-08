from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv  # Для загрузки переменных из .env файла
import os

# Загружаем переменные окружения из .env файла
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ⚠️ ВАЖНО: Секретный ключ. В продакшене лучше хранить в .env файле!
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-e1ib^xo9)vykw1!f%-lydn2*sz4n0j^yd-yey4jh@zuc%3_hsr')

# ⚠️ ВАЖНО: Режим отладки. В продакшене ДОЛЖЕН быть False!
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # Меняем на False для продакшена

# ⚠️ ВАЖНО: Разрешенные хосты. Добавляем наш домен и IP
# ALLOWED_HOSTS = [
#     'prime-forest.ru',
#     'www.prime-forest.ru',
#     '31.31.196.76',  # IP твоего сервера
#     'localhost',      # На всякий случай для тестов
#     '127.0.0.1'       # На всякий случай для тестов
# ]
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Сторонние приложения
    'django_filters',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    
    # Локальные приложения
    'store',
]

# Настройки REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# Настройки JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Настройки CORS
CORS_ALLOW_ALL_ORIGINS = True  # Для разработки разрешаем все источники
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Должен быть в самом верху
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'woodgood.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'woodgood.wsgi.application'

# # Настройки базы данных
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'woodgood',
#         'USER': 'postgres',
#         'PASSWORD': 'postgres',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }
# Настройки базы данных для Docker
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'primeforest_db'),
        'USER': os.getenv('DB_USER', 'primeforest_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'StrongPassword123!'),
        'HOST': os.getenv('DB_HOST', 'postgres'),  # Имя контейнера, не localhost!
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# Модель пользователя
AUTH_USER_MODEL = 'store.User'

# Настройки валидации паролей
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Международные настройки
LANGUAGE_CODE = 'ru-ru'  # Изменено на русский
TIME_ZONE = 'Europe/Moscow'  # Изменено на московское время
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Статические файлы
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ⚠️ ВАЖНО: Настройки безопасности для продакшена
# Эти настройки обязательны для HTTPS
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SECURE_SSL_REDIRECT = True  # Перенаправление с HTTP на HTTPS
# SESSION_COOKIE_SECURE = True  # Куки только по HTTPS
# CSRF_COOKIE_SECURE = True  # CSRF токены только по HTTPS

# Отключаем все HTTPS настройки
SECURE_PROXY_SSL_HEADER = None  # Убираем HTTPS заголовок
SECURE_SSL_REDIRECT = False  # Отключаем редирект на HTTPS
SESSION_COOKIE_SECURE = False  # Куки работают по HTTP
CSRF_COOKIE_SECURE = False  # CSRF токены работают по HTTP

# Настройки CORS для продакшена
# CORS_ALLOW_ALL_ORIGINS = False  # В продакшене запрещаем все источники
# CORS_ALLOWED_ORIGINS = [
#     "https://prime-forest.ru",
#     "https://www.prime-forest.ru",
#     "http://prime-forest.ru",    # На время, пока не настроен HTTPS
#     "http://www.prime-forest.ru", # На время, пока не настроен HTTPS
# ]

# Настройки CORS для разработки
# CORS_ALLOW_ALL_ORIGINS = True  # Разрешаем все для разработки
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
#     "http://localhost:8000",
#     "http://127.0.0.1:8000",
#     "https://prime-forest.ru",
#     "https://www.prime-forest.ru",
# ]

# Разрешаем все CORS
CORS_ALLOW_ALL_ORIGINS = True  # Разрешаем все источники
CORS_ALLOWED_ORIGINS = []  # Пустой список, т.к. разрешаем все

CORS_ALLOW_CREDENTIALS = True

# ⚠️ ВАЖНО: Настройки REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# ⚠️ ВАЖНО: Настройки JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
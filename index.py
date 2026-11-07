# نقطة دخول Vercel: تعرض تطبيق Flask كما هو (المسارات /api/... تعمل كما في التشغيل المحلي)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: E402,F401

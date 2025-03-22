import os
import django
from channels.routing import get_default_application

# 确保在导入其他模块之前设置 Django 设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

application = get_default_application() 
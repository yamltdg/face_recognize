from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/face_recognition/$', consumers.FaceRecognitionConsumer),
    re_path(r'ws/face_record/$', consumers.FaceRecordConsumer),
] 
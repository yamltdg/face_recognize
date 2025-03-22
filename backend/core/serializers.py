from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['stu_id', 'face_id', 'cn_name', 'en_name', 'created_time'] 
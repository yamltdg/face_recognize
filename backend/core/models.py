from django.db import models

class User(models.Model):
    stu_id = models.CharField(max_length=12, primary_key=True)
    face_id = models.IntegerField(default=-1)
    cn_name = models.CharField(max_length=10)
    en_name = models.CharField(max_length=16)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users' 
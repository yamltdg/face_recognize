# Generated by Django 3.2.25 on 2025-01-31 15:43

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('stu_id', models.CharField(max_length=12, primary_key=True, serialize=False)),
                ('face_id', models.IntegerField(default=-1)),
                ('cn_name', models.CharField(max_length=10)),
                ('en_name', models.CharField(max_length=16)),
                ('created_time', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'users',
            },
        ),
    ]

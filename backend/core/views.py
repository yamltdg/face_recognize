import os
import cv2
import numpy as np
import base64
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import User
from .serializers import UserSerializer
import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.db.models import Max
from rest_framework.decorators import api_view

logger = logging.getLogger(__name__)

def cv2_add_chinese_text(img, text, position, font_size=24, color=(0, 0, 255)):
    """在 OpenCV 图片上添加中文文字"""
    # 转换图片从 OpenCV 格式到 PIL 格式
    cv2_im = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_im = Image.fromarray(cv2_im)
    
    # 创建一个可以在给定图像上绘图的对象
    draw = ImageDraw.Draw(pil_im)
    
    # 加载中文字体文件（需要系统中有中文字体）
    fontpath = "/System/Library/Fonts/PingFang.ttc"  # macOS 系统字体路径
    if not os.path.exists(fontpath):
        # 如果找不到 PingFang 字体，尝试其他常见字体
        fontpath = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"  # Linux 系统字体路径
    font = ImageFont.truetype(fontpath, font_size)
    
    # 在图片上添加文字
    draw.text(position, text, font=font, fill=color)
    
    # 转换回 OpenCV 格式
    cv2_text_im = cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)
    
    return cv2_text_im

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_queryset(self):
        logger.debug(f"Query params: {self.request.query_params}")
        queryset = User.objects.all()
        stu_id = self.request.query_params.get('stu_id', None)
        name = self.request.query_params.get('name', None)
        
        if stu_id:
            queryset = queryset.filter(stu_id=stu_id)
        if name:
            queryset = queryset.filter(cn_name__contains=name)
            
        return queryset

    def create(self, request):
        try:
            # 检查是否已存在相同学号的用户
            stu_id = request.data.get('stu_id')
            if User.objects.filter(stu_id=stu_id).exists():
                return Response({'error': '该学号已存在'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 生成新的 face_id
            max_face_id = User.objects.all().aggregate(Max('face_id'))['face_id__max'] or 0
            request.data['face_id'] = max_face_id + 1
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def init_db(self, request):
        logger.debug(f"Received init_db request: {request.data}")
        try:
            # 确保目录存在
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'faces'), exist_ok=True)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'recognizer'), exist_ok=True)
            
            # 清空数据库
            User.objects.all().delete()
            
            return Response({'message': '数据库初始化成功'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def train_model(self,request):
        try:
            print(f"Training with OpenCV version: {cv2.__version__}")
            
            # 获取是否使用直方图均衡化的参数
            equalize_hist = request.data.get('equalize_hist', False)
            print(f"Using histogram equalization: {equalize_hist}")
            
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            faces_dir = os.path.join(settings.MEDIA_ROOT, 'faces')
            
            if not os.path.exists(faces_dir):
                return JsonResponse({
                    'success': False,
                    'error': f'No faces directory found at {faces_dir}'
                })
            
            face_samples = []
            face_ids = []
            
            # 收集训练数据
            for stu_id in os.listdir(faces_dir):
                user_path = os.path.join(faces_dir, stu_id)
                if os.path.isdir(user_path):
                    try:
                        # 获取用户的 face_id
                        user = User.objects.get(stu_id=stu_id)
                        face_id = user.face_id
                        
                        for img_file in os.listdir(user_path):
                            if img_file.endswith('.jpg'):
                                img_path = os.path.join(user_path, img_file)
                                face = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                                
                                # 如果启用了直方图均衡化，则进行处理
                                if equalize_hist and face is not None:
                                    face = cv2.equalizeHist(face)
                                
                                if face is not None and face.shape == (112, 92):
                                    face_samples.append(face)
                                    face_ids.append(face_id)
                                else:
                                    print(f"Skipping invalid image: {img_path}")
                    except User.DoesNotExist:
                        print(f"User not found for stu_id: {stu_id}")
                        continue
            
            if not face_samples:
                return JsonResponse({
                    'success': False,
                    'error': 'No valid face samples found'
                })
            
            try:
                # 训练模型
                print(f"Training with {len(face_samples)} samples")
                recognizer.train(face_samples, np.array(face_ids))
                
                # 保存模型
                recognizer_file = os.path.join(settings.MEDIA_ROOT, 'recognizer/trainingData.yml')
                os.makedirs(os.path.dirname(recognizer_file), exist_ok=True)
                recognizer.write(recognizer_file)
                
                # 验证模型
                test_image = face_samples[0]
                recognizer.predict(test_image)
                
                print("Model trained and verified successfully")
                return JsonResponse({
                    'success': True,
                    'message': f'Model trained with {len(face_samples)} samples'
                })
                
            except Exception as e:
                print(f"Error during training: {str(e)}")
                # 如果训练失败，删除可能损坏的模型文件
                if os.path.exists(recognizer_file):
                    os.remove(recognizer_file)
                return JsonResponse({
                    'success': False,
                    'error': f'Training error: {str(e)}'
                })
                
        except Exception as e:
            print(f"Error in train_model: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

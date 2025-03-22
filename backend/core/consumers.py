import json
import cv2
import base64
import numpy as np
import os
import dlib
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from asgiref.sync import sync_to_async
from .models import User
from PIL import Image

class FaceRecognitionConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("Initializing FaceRecognitionConsumer")
        
        # OpenCV 检测器和识别器
        self.face_cascade = cv2.CascadeClassifier(
            os.path.join(settings.BASE_DIR, 'haarcascades/haarcascade_frontalface_default.xml')
        )
        
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer_file = os.path.join(settings.MEDIA_ROOT, 'recognizer/trainingData.yml')
            if os.path.exists(recognizer_file):
                self.recognizer.read(recognizer_file)
        except Exception as e:
            print(f"Error initializing OpenCV recognizer: {str(e)}")
            self.recognizer = None
        
        # Dlib 检测器和模型
        self.dlib_detector = dlib.get_frontal_face_detector()
        self.shape_predictor = dlib.shape_predictor(
            os.path.join(settings.BASE_DIR, 'dlib/shape_predictor_68_face_landmarks.dat')
        )
        self.face_recognition_model = dlib.face_recognition_model_v1(
            os.path.join(settings.BASE_DIR, 'dlib/dlib_face_recognition_resnet_model_v1.dat')
        )
        
        # 加载已知人脸特征 (用于dlib)
        self.known_face_descriptors = {}
        self.load_known_faces()

    def load_known_faces(self):
        faces_dir = os.path.join(settings.MEDIA_ROOT, 'faces')
        for stu_id in os.listdir(faces_dir):
            user_path = os.path.join(faces_dir, stu_id)
            if os.path.isdir(user_path):
                try:
                    # 获取第一张人脸图片作为参考
                    face_path = os.path.join(user_path, 'face_0.jpg')
                    if os.path.exists(face_path):
                        img = dlib.load_rgb_image(face_path)
                        faces = self.dlib_detector(img)
                        if len(faces) == 1:
                            shape = self.shape_predictor(img, faces[0])
                            face_descriptor = self.face_recognition_model.compute_face_descriptor(img, shape)
                            self.known_face_descriptors[stu_id] = np.array(face_descriptor)
                except Exception as e:
                    print(f"Error loading face for {stu_id}: {str(e)}")

    async def connect(self):
        try:
            await self.accept()
            print(f"WebSocket connected from {self.scope['client']}")
        except Exception as e:
            print(f"WebSocket connection error: {str(e)}")
            return False

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected with code: {close_code}")
        # 清理资源
        if hasattr(self, 'recognizer'):
            self.recognizer = None
        
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            detection_method = data.get('detection_method', 'opencv')
            
            # 解码图像
            image_data = data.get('image').split(',')[1]
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if detection_method == 'dlib':
                # dlib 检测和识别逻辑
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 增加检测参数，提高检测率
                faces = self.dlib_detector(rgb_frame, 1)  # 增加上采样次数
                
                if len(faces) != 1:
                    # 如果没检测到脸，尝试使用 OpenCV 作为备选
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    cv_faces = self.face_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=3,
                        minSize=(30, 30)
                    )
                    
                    if len(cv_faces) == 1:
                        x, y, w, h = cv_faces[0]
                        # 将 OpenCV 检测结果转换为 dlib 矩形
                        face = dlib.rectangle(x, y, x + w, y + h)
                    else:
                        await self.send(text_data=json.dumps({
                            'error': '未检测到人脸或检测到多个人脸',
                            'face_rect': None
                        }))
                        return
                else:
                    face = faces[0]
                
                try:
                    shape = self.shape_predictor(rgb_frame, face)
                    face_descriptor = self.face_recognition_model.compute_face_descriptor(rgb_frame, shape)
                    face_descriptor = np.array(face_descriptor)
                    
                    # 计算与所有已知人脸的距离
                    min_dist = float('inf')
                    matched_stu_id = None
                    
                    for stu_id, known_descriptor in self.known_face_descriptors.items():
                        dist = np.linalg.norm(face_descriptor - known_descriptor)
                        if dist < min_dist:
                            min_dist = dist
                            matched_stu_id = stu_id
                    
                    # 获取关键点坐标
                    landmarks = []
                    for i in range(68):
                        point = shape.part(i)
                        landmarks.append({'x': point.x, 'y': point.y})
                    
                    # 计算相似度
                    similarity = max(0, min(100, (1 - min_dist) * 100))
                    
                    # 构建响应数据
                    response_data = {
                        'face_rect': {
                            'x': face.left(),
                            'y': face.top(),
                            'width': face.right() - face.left(),
                            'height': face.bottom() - face.top()
                        },
                        'landmarks': landmarks,
                        'detection_method': 'dlib'
                    }
                    
                    if matched_stu_id and similarity > 60:
                        user = await sync_to_async(User.objects.get)(stu_id=matched_stu_id)
                        response_data.update({
                            'stu_id': user.stu_id,
                            'cn_name': user.cn_name,
                            'confidence': similarity
                        })
                    else:
                        response_data['error'] = '无法识别的人脸'
                    
                    await self.send(text_data=json.dumps(response_data))
                    
                except Exception as e:
                    print(f"Dlib recognition error: {str(e)}")
                    await self.send(text_data=json.dumps({
                        'error': '人脸识别出错',
                        'face_rect': {
                            'x': face.left(),
                            'y': face.top(),
                            'width': face.right() - face.left(),
                            'height': face.bottom() - face.top()
                        }
                    }))
            else:
                # OpenCV 检测和识别
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=3,
                    minSize=(30, 30)
                )
                
                if len(faces) != 1:
                    await self.send(text_data=json.dumps({
                        'error': '未检测到人脸或检测到多个人脸',
                        'face_rect': None
                    }))
                    return
                
                x, y, w, h = faces[0]
                face_region = gray[y:y+h, x:x+w]
                face_region = cv2.resize(face_region, (92, 112))
                
                try:
                    # 使用 OpenCV 的 LBPH 识别器
                    face_id, confidence = self.recognizer.predict(face_region)
                    user = await sync_to_async(User.objects.get)(face_id=face_id)
                    
                    await self.send(text_data=json.dumps({
                        'face_rect': {
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h)
                        },
                        'stu_id': user.stu_id,
                        'cn_name': user.cn_name,
                        'confidence': float(confidence),
                        'detection_method': 'opencv'
                    }))
                    
                except Exception as e:
                    print(f"OpenCV recognition error: {str(e)}")
                    await self.send(text_data=json.dumps({
                        'error': '人脸识别出错',
                        'face_rect': {
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h)
                        }
                    }))
                
        except Exception as e:
            print(f"Error in receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))
    
    async def send_frame(self, frame, data=None, error=None):
        _, buffer = cv2.imencode('.jpg', frame)
        processed_image = base64.b64encode(buffer).decode('utf-8')
        
        response = {
            'processed_image': f'data:image/jpeg;base64,{processed_image}'
        }
        
        if data:
            response.update(data)
        if error:
            response['error'] = error
            
        await self.send(text_data=json.dumps(response))
    
    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'error': message
        }))
    
    def cv2_add_chinese_text(self, img, text, position, font_size=24, color=(0, 0, 255)):
        # 原有的添加中文文字函数...
        return img 

class FaceRecordConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("Initializing FaceRecordConsumer")
        self.face_cascade = cv2.CascadeClassifier(
            os.path.join(settings.BASE_DIR, 'haarcascades/haarcascade_frontalface_default.xml')
        )
        self.record_count = 0
        self.user_folder = None
        
    async def connect(self):
        await self.accept()
        print("WebSocket connected")

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected with code: {close_code}")
        
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            print(f"Received message type: {data.get('type')}")  # 添加日志
            
            # 处理开始采集的消息
            if data.get('type') == 'start_record':
                self.record_count = 0
                stu_id = data.get('stu_id')
                print(f"Starting record for stu_id: {stu_id}")  # 添加日志
                self.user_folder = os.path.join(settings.MEDIA_ROOT, 'faces', stu_id)
                os.makedirs(self.user_folder, exist_ok=True)
                await self.send(text_data=json.dumps({
                    'type': 'record_started',
                    'message': '开始采集人脸数据'
                }))
                return
                
            # 处理人脸采集请求
            if data.get('type') == 'record_face':
                if self.record_count >= 20:
                    print("Already completed recording")  # 添加日志
                    return
                    
                image_data = data.get('image')
                if not image_data:
                    print("No image data received")  # 添加日志
                    return
                    
                print(f"Processing frame {self.record_count + 1}")  # 添加日志
                
                # 解码Base64图像
                image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                nparr = np.frombuffer(image_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # 人脸检测
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )
                
                if len(faces) != 1:
                    await self.send(text_data=json.dumps({
                        'type': 'face_detect',
                        'error': '未检测到人脸或检测到多个人脸',
                        'face_rect': None
                    }))
                    return
                
                x, y, w, h = faces[0]
                face = gray[y:y+h, x:x+w]
                face = cv2.resize(face, (92, 112))
                
                # 保存人脸图像
                if self.user_folder and self.record_count < 20:
                    filename = f'face_{self.record_count}.jpg'
                    cv2.imwrite(os.path.join(self.user_folder, filename), face)
                    self.record_count += 1
                
                # 发送人脸框位置和采集帧数
                await self.send(text_data=json.dumps({
                    'type': 'face_detect',
                    'face_rect': {
                        'x': int(x),
                        'y': int(y),
                        'width': int(w),
                        'height': int(h)
                    },
                    'record_count': self.record_count
                }))
                
                # 检查是否采集完成
                if self.record_count >= 20:
                    print("Recording completed")  # 添加日志
                    await self.send(text_data=json.dumps({
                        'type': 'record_completed',
                        'message': '人脸数据采集完成'
                    }))
                
        except Exception as e:
            print(f"Error in receive: {str(e)}")  # 保持现有的错误日志
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            })) 
import json
import boto3
import logging
from io import BytesIO
from PIL import Image
import numpy as np
from PIL.ImageOps import exif_transpose
import cv2
import face_recognition
import os
import mariadb

bucket_name = os.getenv('BUCKET_NAME')
db_config = {
    'host': os.getenv('DB_HOST'),  
    'user': os.getenv('DB_USER'),  
    'password': os.getenv('DB_PASSWORD'), 
    'database': os.getenv('DB_NAME')
}

logging.basicConfig(level=logging.INFO)

def load_image_file(file, mode='RGB'):
    try:
        img = Image.open(file)
        img = exif_transpose(img)
        img = img.convert(mode)
        return np.array(img)
    except Exception as e:
        logging.error(f'Error loading image file: {e}')
        return None
    

def download_images_s3(key): 
    try: 
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=bucket_name, Key=key)
        image_data = response['Body'].read()
        return BytesIO(image_data)
    except Exception as e:
        logging.error(f'Error downloading S3 image: {e}')
        return None


def virtual_img(img):
    try:
        pil_image = Image.fromarray(img)
        temp_file = BytesIO()
        pil_image.save(temp_file, format="JPEG")
        temp_file.seek(0)
        return temp_file
    except Exception as e:
        logging.error(f'Error converting image to virtual format: {e}')
        return None

def connect_to_db():
    connection = None
    try:
        connection= mariadb.connect(**db_config)
        return connection
    except Exception as err:
        logging.error(f"Error Database connectio: {err}")
        return None

def validate_gallery_id(gallery_id):
    try:
        return int(gallery_id)
    except ValueError:
        raise ValueError("El gallery_id should be a integer number.")

def get_photos_by_gallery(gallery_id):   
    connection = connect_to_db()
    cursor = None
    photos = []  
    gallery_id = validate_gallery_id(gallery_id)

    if connection:
        try:
            cursor = connection.cursor()
            query = '''
                SELECT 
                    photos.id AS photo_id, 
                    photos_face_recognition.face_location AS face_location, 
                    photos_face_recognition.face_encoding AS face_encoding
                FROM photos
                LEFT JOIN photos_face_recognition ON photos_face_recognition.photo_id = photos.id
                WHERE photos.gallery_id = ?
            '''
            cursor.execute(query, (gallery_id,))  

            rows = cursor.fetchall()
            for row in rows:
                photos.append(row)  
            
            return photos
        except Exception as err:
            print(f"Error getting  photos: {err}")
        finally:
            if cursor:
                cursor.close()  
            if connection:
                connection.close()  

    return photos 


def compare_face(faces, match_face_encoding):
    matched_ids = [] 

    if not faces:
        logging.error("They are not in the selfie.")
        return matched_ids

    face_encodings = []

    for face in faces:
        try:
            encodings = json.loads(face[2]) 
            face_encodings.extend([np.array(enc) for enc in encodings])
        except Exception as e:
            logging.error(f"Error processing locations or encodings: {e}")
            continue

    face_encodings = np.array(face_encodings)

    if face_encodings.size == 0 or match_face_encoding is None:
        logging.error("No facial encodings available for comparison.")
        return matched_ids

    for face_encoding in match_face_encoding:
        try:
            matches = face_recognition.compare_faces(face_encodings, face_encoding)
            face_distances = face_recognition.face_distance(face_encodings, face_encoding)

            for idx, match in enumerate(matches):
                if match: 
                    photo_id = faces[idx][0]
                    matched_ids.append(photo_id)
                logging.debug(f"Index: {idx}, Match: {match}, Distance: {face_distances[idx]}")
        except Exception as e:
            logging.error(f"Error comparing faces: {e}")
            continue

    return matched_ids

def handle_function(event, context):
    try:
        galleryId = event['galleryId']
        key =  event['key']

        if not galleryId:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "galleryId not found"})
            }
        
        if not key:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "key not found"})
            }

        image = download_images_s3(key)
        processed_image = load_image_file(image)
        if processed_image is None:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Error processing the image"})
            }


        resized_image = cv2.resize(processed_image, (640, 640), interpolation=cv2.INTER_AREA)
        image_virtual = virtual_img(resized_image)

        if image_virtual is None:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Error creating virtual image"})
            }

        img_loader = face_recognition.load_image_file(image_virtual) 
        face_locations = face_recognition.face_locations(img_loader, model='cnn')
        face_encodings = face_recognition.face_encodings(img_loader, face_locations)
       
        faces = get_photos_by_gallery(galleryId)
        matches = compare_face(faces, face_encodings)

        image_virtual.close()
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Request processed successfully",
                "match": list(set(matches))
            })
        }


    except Exception as e:
        logging.error(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Error processing the request: {str(e)}"})
        }

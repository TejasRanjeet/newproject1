from flask import Flask, render_template, Response, jsonify
import cv2
import numpy as np
import time
import threading
import pyautogui
import sounddevice as sd

app = Flask(__name__)

# Global variables
face_detector = None
exam_in_progress = False
no_face_start_time = None
multiple_face_start_time = None
exam_termination_event = threading.Event()
exam_window = ""
current_window = ""
noise_level = 0
NOISE_THRESHOLD = 30  # Adjust this value based on your microphone sensitivity

def get_face_detector():
    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    detector = cv2.CascadeClassifier(face_cascade_path)
    if detector.empty():
        raise IOError('Unable to load the face cascade classifier xml file')
    return detector

def detect_faces(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return faces

def draw_faces(frame, faces):
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
    return frame

def generate_frames():
    global exam_in_progress, face_detector, no_face_start_time, multiple_face_start_time, exam_window, current_window, noise_level
    
    if face_detector is None:
        face_detector = get_face_detector()
    
    cap = cv2.VideoCapture(0)
    
    while not exam_termination_event.is_set():
        success, frame = cap.read()
        if not success:
            break
        else:
            faces = detect_faces(frame)
            face_count = len(faces)
            frame = draw_faces(frame, faces)

            if face_count == 0:
                if no_face_start_time is None:
                    no_face_start_time = time.time()
                elif time.time() - no_face_start_time > 5:  # 5 seconds threshold
                    cv2.putText(frame, 'No face detected. Terminating exam.', (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    exam_termination_event.set()
                else:
                    cv2.putText(frame, 'Warning: No face detected!', (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            elif face_count > 1 :
                if multiple_face_start_time is None:
                    multiple_face_start_time = time.time()
                elif time.time() - multiple_face_start_time > 5:  # 5 seconds threshold
                    cv2.putText(frame, 'Multiple face detected. Terminating exam.', (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    exam_termination_event.set()
                else:
                    cv2.putText(frame, 'Warning: Multiple face detected!', (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                no_face_start_time = None
                multiple_face_start_time = None

            cv2.putText(frame, f'Faces detected: {face_count}', (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Add current window and noise level to the frame
            cv2.putText(frame, f'Current window: {current_window}', (10, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            cv2.putText(frame, f'Noise level: {noise_level}', (10, 120), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            # Check for tab switch or excessive noise
            if exam_in_progress:
                if current_window != exam_window:
                    cv2.putText(frame, 'Tab switch detected. Terminating exam.', (10, 150), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    exam_termination_event.set()

                if noise_level > NOISE_THRESHOLD:
                    cv2.putText(frame, 'Excessive noise detected. Terminating exam.', (10, 180), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    exam_termination_event.set()

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

def monitor_screen():
    global exam_window, current_window, exam_termination_event, exam_in_progress
    
    # Wait for the exam to start
    while not exam_in_progress:
        time.sleep(1)
    
    # Give the user 5 seconds to switch to the exam window
    time.sleep(5)
    
    # Set the exam window
    exam_window = pyautogui.getActiveWindowTitle()
    print(f"Exam window: {exam_window}")
    
    while not exam_termination_event.is_set():
        current_window = pyautogui.getActiveWindowTitle()
        if current_window != exam_window:
            print(f"Tab switch detected. From {exam_window} to {current_window}")
            exam_termination_event.set()
        time.sleep(1)

def audio_callback(indata, frames, time, status):
    global noise_level, exam_termination_event
    volume_norm = np.linalg.norm(indata) * 10
    noise_level = int(volume_norm)
    if noise_level > NOISE_THRESHOLD:
        print(f"Excessive noise detected: {noise_level}")
        exam_termination_event.set()

def monitor_audio():
    with sd.InputStream(callback=audio_callback):
        sd.sleep(1000000)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_exam')
def start_exam():
    global exam_in_progress, exam_termination_event
    if not exam_in_progress:
        exam_in_progress = True
        exam_termination_event.clear()
        threading.Thread(target=monitor_screen, daemon=True).start()
        threading.Thread(target=monitor_audio, daemon=True).start()
        return jsonify({"status": "Exam started. Please switch to the exam window within 5 seconds."})
    else:
        return jsonify({"status": "Exam already in progress"})

@app.route('/end_exam')
def end_exam():
    global exam_in_progress, exam_termination_event
    exam_in_progress = False
    exam_termination_event.set()
    return jsonify({"status": "Exam ended"})

@app.route('/check_status')
def check_status():
    global exam_in_progress, exam_termination_event, current_window, noise_level
    status = {
        "exam_in_progress": exam_in_progress,
        "exam_terminated": exam_termination_event.is_set(),
        "current_window": current_window,
        "noise_level": noise_level
    }
    return jsonify(status)

if __name__ == '__main__':
    print("Starting the Flask server...")
    print("Once the server is running, open a web browser and go to http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
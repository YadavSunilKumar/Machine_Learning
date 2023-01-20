#!/usr/bin/env python
from threading import Thread, Lock
import xml.etree.ElementTree as ET
import cv2

class Camera :
    def __init__(self, cameraID, url) :
        self.cameraID = cameraID
        self.url = url
        self.analytics_type = analytics_type
        self.cap = cv2.VideoCapture(url)

        self.cap = cv2.VideoCapture(url)
        self.counter = 0
        # self.cap.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 1280)
        # self.cap.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 720)

        (_, self.frame) = self.cap.read()
        self.started = False
        self.read_lock = Lock()

    def start(self) :
        self.thread = Thread(target=self.frame_update, args=())
        self.thread.start()
        return self

    def frame_update(self) :
        while True:
            (_, frame) = self.cap.read()
            self.read_lock.acquire()
            self.counter += 1
            print('counter: ', self.counter)
            self.frame = frame
            self.read_lock.release()

    def read(self) :
        self.read_lock.acquire()
        frame = self.frame.copy()
        self.read_lock.release()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame = cv2.resize(gray, (640, 360))
        frame = cv2.equalizeHist(frame)

        return frame, self.cameraID

    def stop(self) :
        self.started = False
        self.thread.join()

    def __exit__(self, exc_type, exc_value, traceback) :
        self.cap.release()

if __name__ == "__main__" :
  tree = ET.parse('config_main.xml')
  configuration = tree.getroot()

  cams = []
  for cameras in configuration.findall('CAMERA'):
    camera_id = cameras.find('CAMERA_ID').text
    url = cameras.find('URL').text
    #url = cameras.find('1.mp4').text
    analytics_type = cameras.find('ANALYTICS_TYPE').text
    cam = Camera(camera_id, url).start()
    cams.append(cam)

  while True :
    for thread in cams:
      frame, camera_id = thread.read()
      cv2.imshow(camera_id, frame)
      cv2.waitKey(100)

    # cam.stop()
    # cv2.destroyAllWindows()
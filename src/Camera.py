import threading
import threading as td
import cv2
import queue
import time
from imutils.video import FileVideoStream


class Camera(td.Thread):
    # initialization
    def __init__(self, siteId, appId, cameraID, cameraName, url, cam_config, main_config, yolo_model, args):
        # print("Initialization camera:"+cameraID)
        td.Thread.__init__(self)

        self.parameters = siteId, appId, cameraID, cameraName, url, cam_config, main_config, yolo_model, args
        self.siteId = siteId
        self.appId = appId
        self.cameraID = cameraID
        self.url = url
        self.reconnect_count = 0
        self.restart = False
        self.close_thread = False
        print("CAMERA STARTED : ", cameraID, " ", self.reconnect_count, " ", self.restart, " ", hex(id(self)))
        self.cam_config = cam_config
        self.analytics_type = main_config.analytics_type
        from HawkerDetection import HawkerDetection as Analytics
        self.analytics = Analytics(siteId, appId, cameraID, cameraName, cam_config, main_config, yolo_model, args)
        self.cap = FileVideoStream(path=url, queue_size=100).start()
        # self.cap = cv2.VideoCapture(url)
        self.frameQueue = queue.Queue(100)
        self.frameQueueLock = td.Lock()
        try:
            td.Thread(target=self.threadedFunction).start()
            # td.Thread(target=self.display).start()
            # print("Started new Thread")
        except:
            print("Process thread not created")

    # run in thread
    def run(self):
        # print("Running thread")
        while (1):
            time.sleep(0.033)
            if self.close_thread:
                print('Stopping Camera: ', self.cameraID)
                break
            # time.sleep(0.100)
            # print("Camera Id : "+self.cameraID)
            # ret, frame = self.cap.read()
            if self.cap.running():
                frame = self.cap.read()
                self.frameQueueLock.acquire()
                self.frameQueue.put(frame)
                self.frameQueueLock.release()
            else:
                if self.reconnect_count >= 5:
                    self.restart = True
                else:
                    print("Reconnecting camera: {}".format(self.cameraID))
                    print("ID: ", hex(id(self)))
                    self.reconnect_count = self.reconnect_count + 1
                    self.cap.stop()
                    self.cap = FileVideoStream(path=self.url, queue_size=100).start()
            # print("Interted in queue")
            # time.sleep(0.060)

    # Processing Thread
    def threadedFunction(self):
        while (1):
            # print("Queue Size is : %d"%self.frameQueue.qsize())
            if self.frameQueue.qsize() >= 1:
                # print("Get from queue")
                self.frameQueueLock.acquire()
                frame = self.frameQueue.get()
                self.frameQueueLock.release()
                # print("Queue unlocked")
                # print("Calling frame process")
                # print(len(frame))
                if frame is not None:
                    self.analytics.frameProcess(frame)
                else:
                    time.sleep(0.5)
            else:
                time.sleep(0.01)

    # Function to process image
    # def frameProcessing(self,frame):
    #     gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #     resized_image = cv2.resize(gray, (1280, 720))
    #     equ = cv2.equalizeHist(resized_image)
    #
    #     # fgmask = self.fgbg.apply(equ)
    #     self.displayLock.acquire()
    #     self.displayImage = equ
    #     self.displayLock.release()

    def display(self):
        self.analytics.display()

import cv2
import json
import sys
import os
from threading import Thread, Lock
import argparse
import imutils


class PlayCamera:
    def __init__(self, url, height, width):
        self.cap = cv2.VideoCapture(url)
        self.key = -1
        self.play = True
        self.end = False
        self.points = []
        self.width = width
        self.height = height
        self.winName = "SELECT POINTS"

    def onMouse(self, event, x, y, flags, param):
        self.currentPos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))
        elif event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))

    def playStream(self):
        frame = []
        while True:
            if self.play:
                _, frame = self.cap.read()
                self.img = frame.copy()
            else:
                if len(frame):
                    self.img = frame.copy()
            if len(self.img):
                rzimg = cv2.resize(self.img, (int(self.width), int(self.height)))
                # cv2.namedWindow(winName, cv2.WINDOW_AUTOSIZE)
                if self.points.__len__() > 1:
                    for i in range(1, len(self.points)):
                        cv2.line(rzimg, self.points[i - 1], self.points[i], (255, 255, 0), 2, 8)

                cv2.namedWindow(self.winName, cv2.WINDOW_NORMAL)
                cv2.setMouseCallback(self.winName, self.onMouse)
            cv2.imshow(self.winName, rzimg)
            key = cv2.waitKey(40)
            if key == 32:
                self.play = not self.play
            if key == 27:
                for point in self.points:
                    print('<POINT X="%d" Y="%d"/>'%(point[0],point[1]))
                self.cap.release()
                cv2.destroyAllWindows()
                break

if __name__ == '__main__':

    # playCamera = PlayCamera("/home/secura/Downloads/vlc-record-2018-12-21-16h55m01s-rtsp___192.168.1.144-.mp4")
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="INPUT VIDEO URL")
    parser.add_argument("--height", help="height", default=720)
    parser.add_argument("--width", help="width", default=1280)

    args = parser.parse_args()

    playCamera = PlayCamera(str(args.url), args.height, args.width)

    # print(playCamera.playStream())
    playCamera.playStream()
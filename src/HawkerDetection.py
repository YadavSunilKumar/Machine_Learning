import cv2
import threading as td
import numpy as np
import time as t
import datetime
import json, math
import os
import errno
import urllib.request
from collections import deque
from time import time
from model import utils
import sys
from utils import Log

Log = Log()


# class BlockZone:
#     def __init__(self, points, threshold):
#         self.points = points
#         self.thresholdValue = threshold
#         self.status = False
#         self.previousStatus = False


class HawkingZone:
    def __init__(self, zoneId, points, queue_max_len):
        self.zoneId = zoneId
        self.points = points
        self.status = False
        self.currentStatus = False
        self.initialized = False
        self.confidence_list = []
        self.status_queue = deque(maxlen=queue_max_len)
        self.check_count = 0
        self.status_list = []
        self.previous_evidence_image_path = None


class AllowedRegion:
    def __init__(self, points, time):
        self.points = points
        self.time = time

    def isAllowedTime(self):
        frm = self.time[0].split(':')
        to = self.time[1].split(':')
        current = t.localtime()
        fromTime = (int(frm[0]) * 100) + (int(frm[1]))
        toTime = (int(to[0]) * 100) + (int(to[1]))
        curTime = (current.tm_hour * 100) + (current.tm_min)
        if (curTime >= fromTime) and (curTime <= toTime):
            return True
        else:
            return False


class MedianImage:
    def __init__(self, stackSize: int):
        self.__imageQueue = deque(maxlen=stackSize)

    def push_image(self, image):
        self.__imageQueue.append(image)

    def get_median_image(self) -> np.ndarray:
        sequence = np.stack(tuple(self.__imageQueue), axis=3)
        result = np.median(sequence, axis=3).astype(np.uint8)
        return result

    def get_queue_size(self) -> int:
        return self.__imageQueue.__len__()

    def clear(self):
        self.__imageQueue.clear()


class HawkerDetection:
    # Calls when initialized
    trackerObjects = []

    def __init__(self, siteId, appId, cameraId, cameraName, cam_config, main_config, yolo_model, args):
        self.countFrames = 0
        self.confidence = 0
        self.args = args
        self.draw_rect = False
        self.siteId = siteId
        self.displayFrame = None
        self.appId = appId
        self.cameraId = cameraId
        self.cameraName = cameraName
        self.config = cam_config
        self.main_config = main_config
        self.loadConfiguration()
        self.postRequestSetup()
        self.displayLock = td.Lock()
        self.analyticstype = main_config.analytics_type
        self.wrongpark = False
        self.startclock = False
        self.appStarted = True
        self.zoneDir = {}
        self.medianimage = MedianImage(self.config.static_frames)
        self.fgbg = cv2.createBackgroundSubtractorMOG2()
        self.output = []
        self.yolo_model = yolo_model
        self.post_every_request = args.post_every_request
        self.dump_images = args.dump_images

    # To load configurations
    def loadConfiguration(self):

        self.framesize = (int(self.config.width), int(self.config.height))
        self.confidence = self.config.confidence
        self.draw_rect = self.main_config.draw_rect
        self.zones = []
        for zone in self.config.zones:
            zoneId = zone.zone_name
            points = []
            for point in zone.points:
                pt = [int(point.x), int(point.y)]
                points.append(pt)
            HkwZone = HawkingZone(zoneId, points, self.config.queue_size)
            self.zones.append(HkwZone)

        self.allowedAreas = []

    # SetUp Post Request
    def postRequestSetup(self):
        self.req = urllib.request.Request(self.main_config.post_url)
        self.req.add_header('Content-Type', 'application/json; charset=utf-8')

    # Used for Masking zone
    def makeMaskForZone(self, frame, zone, invert):
        mask = np.zeros(frame.shape, dtype=np.uint8)
        roi_corners = np.array([zone], dtype=np.int32)
        ignore_mask_color = (255,)  # *channel_count
        cv2.fillPoly(mask, roi_corners, ignore_mask_color)
        if invert:
            mask = cv2.bitwise_not(mask)
        masked_image = cv2.bitwise_and(mask, frame)
        return masked_image

    def intersects_ctr(self, zone_rect, hawker_rects, intersect_pixel):
        try:
            for hawker_rect in hawker_rects:
                if len(hawker_rect) != 0:  # check tuple null or not
                    zone_ctr = np.array(zone_rect).reshape((-1, 1, 2)).astype(np.int32)
                    distance = cv2.pointPolygonTest(contour=zone_ctr, pt=hawker_rect, measureDist=True)
                    if distance >= intersect_pixel:
                        return True
            return False

        except Exception as e:
            Log.exception(str(e))
            return False

    def detectObjectUsingImageProcessing(self, static_frame, org_frame):
        resizedFrame = cv2.resize(static_frame, self.framesize)
        org_frame_resized = cv2.resize(org_frame, self.framesize)
        predict_outs = self.yolo_model.predict(resizedFrame)
        classes = utils.read_class_names(self.main_config.model_names_path)
        new_predict_outs = []

        for prediction in predict_outs:
            x_min, y_min, x_max, y_max, probability, cls_id = prediction
            if classes[cls_id] in self.main_config.white_list:
                new_predict_outs.append(prediction)

        if self.draw_rect is True:
            self.output = utils.draw_bbox(org_frame_resized.copy(), new_predict_outs,
                                          classes_path=self.main_config.model_names_path,
                                          show_label=self.draw_rect,
                                          confidence=self.confidence)
        else:
            self.output = org_frame_resized
        for zone_index, Hkwnzone in enumerate(self.zones):
            self.zoneDir[Hkwnzone.zoneId] = Hkwnzone.status
            zone_points = Hkwnzone.points
            hawker_in_zone_status = False
            hawker_detected_rects = []
            for x_min, y_min, x_max, y_max, probability, cls_id in new_predict_outs:
                haker_rects = [(x_min, y_min), (int((x_max + x_min) / 2), y_min), (x_max, y_min),
                               (x_max, int((y_max + y_min) / 2)), (x_max, y_max), (int((x_max + x_min) / 2), y_max),
                               (x_min, y_max), (x_min, int((y_max + y_min) / 2)), ()]

                if probability >= self.confidence and self.intersects_ctr(zone_rect=zone_points,
                                                                          hawker_rects=haker_rects,
                                                                          intersect_pixel=self.config.intersect_pixel):
                    hawker_in_zone_status = True
                    hawker_detected_rects.append(
                        {"x_min": round(x_min, 2), "y_min": round(y_min, 2), "x_max": round(x_max, 2),
                         "y_max": round(y_max, 2), "probability": round(probability, 2)})
            Hkwnzone.status_queue.append(hawker_in_zone_status)
            # print(Hkwnzone.status_queue, " | CURRENT HAWKER:", hawker_in_zone_status)
            Hkwnzone.check_count += 1
            true_count = Hkwnzone.status_queue.count(True)  # COUNTER STARTED WITH 0
            false_count = Hkwnzone.status_queue.count(False)  # COUNTER STARTED WITH 0
            print("CAMERA NAME: ", self.cameraName, " | CAMERA ID: ", self.cameraId, " | ZONE: ", Hkwnzone.zoneId,
                  " | CURRENT HAWKER:", hawker_in_zone_status, "| (True/False", true_count, "/", false_count, ")",
                  " | CHECK: ", Hkwnzone.check_count)
            # if true_count >= self.config.number_of_check or false_count >= self.config.number_of_check:
            if Hkwnzone.check_count >= self.config.number_of_check:
                Hkwnzone.currentStatus = True if true_count > false_count else False
                if hawker_in_zone_status is Hkwnzone.currentStatus:
                    if (True if self.post_every_request else (
                                                                     Hkwnzone.status is not Hkwnzone.currentStatus) or Hkwnzone.initialized is False):
                        Hkwnzone.status = Hkwnzone.currentStatus
                        Hkwnzone.initialized = True
                        thread = td.Thread(target=self.sendPostAndSaveImage,
                                           args=[org_frame_resized.copy(), self.siteId, self.appId, self.cameraId,
                                                 Hkwnzone,
                                                 t.localtime(), Hkwnzone.status, self.output.copy(),
                                                 static_frame.copy(),
                                                 hawker_detected_rects])
                        thread.setDaemon(True)
                        thread.start()
                    Hkwnzone.check_count = 0
                    Hkwnzone.currentStatus = False
                else:
                    print("RECHECKING | ", "CAMERA NAME: ", self.cameraName, " | CAMERA ID: ", self.cameraId,
                          " | ZONE: ",
                          Hkwnzone.zoneId,
                          " | Queue status: ", Hkwnzone.currentStatus, " | Current status: ", hawker_in_zone_status,
                          "| (True/False", true_count, "/", false_count, ")")
                # Hkwnzone.status_list = []  # reset status list

            # old logic
            # self.zoneDir[Hkwnzone.zoneId] = Hkwnzone.status
            # Hkwnzone.sum = 0
            # zone_points = Hkwnzone.points
            # hawker_in_zone_status = False
            # Hkwnzone.confidence_list.insert(Hkwnzone.check_count, 0)  # init confidence
            # for x_min, y_min, x_max, y_max, probability, cls_id in predict_outs:
            #     haker_rects = [(x_min, y_min), (int((x_max + x_min) / 2), y_min), (x_max, y_min),
            #                    (x_max, int((y_max + y_min) / 2)), (x_max, y_max), (int((x_max + x_min) / 2), y_max),
            #                    (x_min, y_max), (x_min, int((y_max + y_min) / 2)), ()]
            #     if probability >= self.confidence and self.intersects_ctr(zone_rect=zone_points,
            #                                                               hawker_rects=haker_rects,
            #                                                               intersect_pixel=self.config.intersect_pixel):
            #         hawker_in_zone_status = True
            #
            #         # confidence logic
            #         try:
            #             if probability > Hkwnzone.confidence_list[Hkwnzone.check_count]:
            #                 Hkwnzone.confidence_list[Hkwnzone.check_count] = probability
            #         except:
            #             pass
            # Hkwnzone.status_list.append(hawker_in_zone_status)
            # Hkwnzone.check_count += 1
            #
            # try:
            #     if self.args.dump is True:
            #         self.dumpDebugImage(frame=self.output.copy(), siteId=self.siteId, appId=self.appId,
            #                             cameraId=self.cameraId, zone=Hkwnzone, time=t.localtime(),
            #                             status=Hkwnzone.status, static_img=resizedFrame.copy(),
            #                             count=Hkwnzone.check_count)
            # except Exception as e:
            #     print("DUMP : EXCEPTION :: ", e)
            #
            # if Hkwnzone.check_count >= self.config.number_of_check:
            #     true_count = Hkwnzone.status_list.count(True)
            #     false_count = Hkwnzone.status_list.count(False)
            #     Hkwnzone.previousStatus = True if true_count >= false_count else False
            #     if Hkwnzone.status is not Hkwnzone.previousStatus or Hkwnzone.initialized is False:
            #         Hkwnzone.status = Hkwnzone.previousStatus
            #         Hkwnzone.initialized = True
            #         thread = td.Thread(target=self.sendPostAndSaveImage,
            #                            args=[org_frame_resized.copy(), self.siteId, self.appId, self.cameraId, Hkwnzone,
            #                                  t.localtime(), Hkwnzone.status, self.output.copy()])
            #         thread.setDaemon(True)
            #         thread.start()
            #     Hkwnzone.check_count = 0
            #     Hkwnzone.previousStatus = False
            #     Hkwnzone.status_list = []  # reset status list
            #     Hkwnzone.confidence_list = []  # reset confidence list

        return resizedFrame

    # def dumpDebugImage(self, frame, siteId, appId, cameraId, zone, time, status, static_img, count=0):
    #
    #     fixPath = self.main_config.storage_path + "Debug/"
    #     newFrame = frame.copy()
    #
    #     if status:
    #         color = (0, 0, 255)
    #     else:
    #         color = (255, 255, 255)
    #
    #     pts = np.array(zone.points, np.int32)
    #     pts = pts.reshape((-1, 1, 2))
    #     cv2.polylines(newFrame, [pts], True, color, 8)
    #     timeStamp = str(
    #         math.floor((datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(0)).total_seconds() * 1000.0))
    #
    #     date = str(time.tm_year) + str(time.tm_mon) + str('{:02}'.format(time.tm_mday))
    #
    #     evidenceName = 'Evi_' + str(siteId) + '_' + str(cameraId) + '_' + str(
    #         zone.zoneId) + '_' + timeStamp + '.jpg'
    #     evidenceName = evidenceName.replace(':', '')
    #     folderPath = str(siteId) + '/' + str(appId) + '/' + str(cameraId) + '/HAWKING_DETECTION/' + date
    #     sendfolderPath = str(appId) + '/' + str(cameraId) + '/HAWKING_DETECTION/' + date
    #
    #     if not os.path.exists(os.path.dirname(fixPath + folderPath + '/Evidence/' + evidenceName)):
    #         try:
    #             os.makedirs(os.path.dirname(fixPath + folderPath + '/Evidence/' + evidenceName))
    #         except OSError as exc:
    #             if exc.errno != errno.EEXIST:
    #                 raise
    #     cv2.imwrite(
    #         fixPath + folderPath + '/Evidence/' + evidenceName.replace('.jpg', "_" + str(status) + '_debug_' + str(
    #             count) + '.jpg'),
    #         newFrame)
    #     cv2.imwrite(
    #         fixPath + folderPath + '/Evidence/' + evidenceName.replace('.jpg', "_" + str(status) + '_static_' + str(
    #             count) + '.jpg'),
    #         static_img)
    #
    #     #############################

    def sendPostAndSaveImage(self, frame, siteId, appId, cameraId, zone, time, status, output, static_frame,
                             hawker_detected_rects):
        fixPath = self.main_config.storage_path
        newFrame = frame.copy()

        if status:
            color = (0, 0, 255)
        else:
            color = (255, 255, 255)

        pts = np.array(zone.points, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(newFrame, [pts], True, color, 8)
        timeStamp = str(
            math.floor((datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(0)).total_seconds() * 1000.0))

        date = str(time.tm_year) + str(time.tm_mon) + str('{:02}'.format(time.tm_mday))

        evidenceName = 'Evi_' + str(siteId) + '_' + str(cameraId) + '_' + str(zone.zoneId) + '_' + timeStamp + '.jpg'
        evidenceName = evidenceName.replace(':', '')
        folderPath = str(siteId) + '/' + str(appId) + '/' + str(cameraId) + '/HAWKING_DETECTION/' + date
        sendfolderPath = str(appId) + '/' + str(cameraId) + '/HAWKING_DETECTION/' + date

        if not os.path.exists(os.path.dirname(fixPath + folderPath + '/Evidence/' + evidenceName)):
            try:
                os.makedirs(os.path.dirname(fixPath + folderPath + '/Evidence/' + evidenceName))
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
        cv2.imwrite(fixPath + folderPath + '/Evidence/' + evidenceName, newFrame)
        if self.dump_images:
            cv2.imwrite(
                fixPath + folderPath + '/Evidence/' + evidenceName.replace('.jpg', "_" + str(status) + '_train.jpg'),
                frame)
            cv2.imwrite(
                fixPath + folderPath + '/Evidence/' + evidenceName.replace('.jpg', "_" + str(status) + '_static.jpg'),
                static_frame)
        if self.draw_rect is True:
            cv2.imwrite(fixPath + folderPath + '/Evidence/' + evidenceName.replace('.jpg', "_rect.jpg"), output)
        body = {}
        body['analyticsType'] = self.main_config.analytics_type
        body['sourceLocation'] = siteId
        body['camGUID'] = cameraId
        body['camName'] = self.cameraName
        body['confidence'] = ''
        body['zoneId'] = zone.zoneId
        if status:
            body['status'] = 1
            body['hawker_rects'] = hawker_detected_rects
            body['hawkingImagePath'] = sendfolderPath + '/Evidence/' + evidenceName
        else:
            body['status'] = 0
            body['hawkingImagePath'] = sendfolderPath + '/Evidence/' + evidenceName
        body['timeStamp'] = timeStamp
        jsondata = json.dumps(body)
        jsondataasbytes = jsondata.encode('utf-8')
        self.req.add_header('Content-Length', str(len(jsondataasbytes)))
        Log.print('Json send to server: ' + str(jsondata))
        # sys.stdout.flush()
        try:
            response = urllib.request.urlopen(self.req, jsondataasbytes, timeout=20)
            response_data = response.read()
            data = json.loads(response_data)
            Log.print('Received response :' + str(data))
            # sys.stdout.flush()
        except Exception as e:
            Log.exception('Unable to post URL :: ' + str(e))
            # sys.stdout.flush()

    def get_Time(self):
        dt_string = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return dt_string

    # Frame processing
    def frameProcess(self, frame):
        self.countFrames += 1
        org_frame = frame.copy()
        # WITH STATIC IMAGE
        if (self.countFrames % self.config.skip_frames) == 0:
            self.medianimage.push_image(frame)
            if self.medianimage.get_queue_size() == self.config.static_frames:
                frame = self.medianimage.get_median_image()
                start_time = int(round(time() * 1000))
                out = self.detectObjectUsingImageProcessing(frame, org_frame)
                end_time = int(round(time() * 1000))
                ms_time = (end_time - start_time)
                Log.print("CAMERA NAME : " + str(self.cameraName) + " :: FRAME COUNT : " +
                          str(self.countFrames) + " :: PROCESS : " + str(ms_time))
                # sys.stdout.flush()
            else:
                out = cv2.resize(frame, self.framesize)
        else:
            out = cv2.resize(frame, self.framesize)

        # WITHOUT STATIC IMAGE
        # if (self.countFrames % self.skipFrames) == 0:
        #     out = self.detectObjectUsingImageProcessing(frame)
        # else:
        #     out = cv2.resize(frame, self.framesize)

        self.displayLock.acquire()
        self.displayFrame = out
        # self.output = subFrameThresh
        self.displayLock.release()

    # Called by display in main
    def display(self):
        if self.main_config.debug is True and self.displayFrame is not None:
            self.displayLock.acquire()
            drawFrame = self.displayFrame
            self.displayLock.release()

            def onClick(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDBLCLK:
                    print('x: ', x, 'y: ', y)
                    sys.stdout.flush()

            for Hkwnzone in self.zones:
                if Hkwnzone.status:
                    color = (0, 0, 255)
                else:
                    color = (255, 255, 255)
                pts = np.array(Hkwnzone.points, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(drawFrame, [pts], True, color, 8)
            if self.config.enable_green_zone == 1 or self.main_config.debug is True:
                for allowableRegion in self.allowedAreas:
                    if allowableRegion.isAllowedTime():
                        color = (0, 255, 0)
                        pts = np.array(allowableRegion.points, np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(drawFrame, [pts], True, color, 8)
            cv2.namedWindow(self.cameraId, cv2.WINDOW_NORMAL)
            cv2.imshow(self.cameraId, drawFrame)
            cv2.waitKey(1)

            if len(self.output) and self.main_config.debug is True:
                cv2.namedWindow(self.cameraId + '_output', cv2.WINDOW_NORMAL)
                cv2.imshow(self.cameraId + '_output', self.output)
                cv2.waitKey(1)

            if self.main_config.debug is True:
                cv2.setMouseCallback(self.cameraId, onClick)

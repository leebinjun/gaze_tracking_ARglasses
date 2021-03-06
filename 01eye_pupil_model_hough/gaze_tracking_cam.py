import cv2
import numpy as np
import os
import time


class GazeTracking(object):

    def __init__(self, frame, average_iris_size = 0.20):
        self.frame = frame
        self.average_iris_size = average_iris_size

    @staticmethod
    def pupil_size(iris_frame):
        """
        返回虹膜占据眼睛的表面空间的百分比。
        """
        height, width = iris_frame.shape[:2]
        nb_pixels = height * width
        nb_blacks = nb_pixels - cv2.countNonZero(iris_frame)  # 虹膜像素数
        return nb_blacks / nb_pixels

    @staticmethod
    def image_processing(frame, threshold):
        # 双边滤波 邻域直径:10，空间高斯函数标准差:15，灰度值相似性高斯函数标准差:15
        new_frame = cv2.bilateralFilter(frame, 10, 15, 15)

        # 腐蚀
        # iteration的值越高，模糊程度(腐蚀程度)就越高呈正相关关系
        # 感觉不用 腐蚀 的话，识别度跟高
        kernel = np.ones((3, 3), np.uint8)
        new_frame = cv2.erode(new_frame, kernel, iterations=3)
        # cv2.imwrite("data/eye_frame_bilateralFilter_erode.jpg", new_frame)

        new_frame = cv2.threshold(new_frame, threshold, 255, cv2.THRESH_BINARY)[1]

        return new_frame

    def find_best_threshold(self, frame):
        trials = {}

        for threshold in range(30, 100, 2):
            iris_frame = self.image_processing(frame, threshold)
            trials[threshold] = self.pupil_size(iris_frame)

        # 以 abs(iris_size - average_iris_size) 为关键，求最小项
        best_threshold, iris_size = min(trials.items(), key=(lambda p: abs(p[1] - self.average_iris_size)))

        return best_threshold

    def pretreat(self):
        # 裁切图片
        height, width = self.frame.shape[:2]
        self.frame = self.frame[10:height-10, 150:width-50]

        # 缩小尺寸
        self.frame = cv2.resize(self.frame, (int(width / 10), int(height / 10)))

        # 灰度化，双边滤波
        self.gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        new_frame = cv2.bilateralFilter(self.gray, 10, 15, 15)
        # cv2.imshow("bilateralFilter", new_frame)
        return new_frame

    @staticmethod
    def add_border(new_frame):
        # 加白边
        height, width = new_frame.shape[:2]
        white_l = 255 * np.ones((height, 2), np.uint8)  # 白底左右
        white_t = 255 * np.ones((2, width + 4), np.uint8)  # 白底上下

        new_frame = np.concatenate((new_frame, white_l), axis=1)
        new_frame = np.concatenate((white_l, new_frame), axis=1)
        new_frame = np.concatenate((new_frame, white_t), axis=0)
        new_frame = np.concatenate((white_t, new_frame), axis=0)

        return new_frame

    @staticmethod
    def find_iris_cnt(new_frame):
        # 从二值化虹膜图像中找出轮廓
        _, contours, _ = cv2.findContours(new_frame, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        # 将找出的轮廓按面积排序
        contours = sorted(contours, key=cv2.contourArea)
        # 虹膜即为面积第二大的
        iris_cnt = contours[-2]

        # 提取轮廓面积前2大的
        iris_frame = cv2.cvtColor(new_frame.copy(), cv2.COLOR_BAYER_GR2BGR)
        imag_2 = cv2.drawContours(iris_frame.copy(), [contours[-2]], 0, (0, 255, 0), 2)
        imag_1 = cv2.drawContours(iris_frame.copy(), [contours[-1]], 0, (255, 0, 0), 2)
        # cv2.imshow("contours_2", imag_2)
        # cv2.imshow("contours_1", imag_1)

        return iris_cnt

    def detect_iris(self, iris_cnt):
        x, y = 0, 0
        # 计算质心
        try:
            # 提取轮廓几何特征，计算质心
            moments = cv2.moments(iris_cnt)
            x = int(moments['m10'] / moments['m00'])
            y = int(moments['m01'] / moments['m00'])
        except (IndexError, ZeroDivisionError):
            pass

        # (x, y), radius = cv2.minEnclosingCircle(iris_cnt)
        # (x, y) = (int(x), int(y))
        # 画十字标

        color = (0, 255, 0)

        cv2.line(self.frame, (x - 3, y), (x + 3, y), color, thickness=2)
        cv2.line(self.frame, (x, y - 3), (x, y + 3), color, thickness=2)
        cv2.imshow("target", self.frame)

    def hough(self, frame):
        img = self.frame.copy()
        circle1 = cv2.HoughCircles(frame, cv2.HOUGH_GRADIENT, 1, 80, param1=10, param2=3, minRadius=5,
                                   maxRadius=12)  # 把半径范围缩小点，检测内圆，瞳孔

        try:
            circles = circle1[0, :, :]  # 提取为二维
            circles = np.uint16(np.around(circles))  # 四舍五入，取整
            for i in circles[:]:
                self.x, self.y = i[0], i[1]
                cv2.circle(img, (i[0], i[1]), i[2], (255, 0, 0), 2)  # 画圆
                print(i[2])
                cv2.circle(img, (i[0], i[1]), 2, (255, 0, 0), 1)  # 画圆心
        except:
            print("未检测到瞳孔")
            self.x, self.y = 0, 0

        # t = str(time.time())
        cv2.imshow("hough", img)

        # x, y = self.x, self.y
        #
        # color = (0, 255, 0)
        #
        # cv2.line(self.frame, (x - 3, y), (x + 3, y), color, thickness=2)
        # cv2.line(self.frame, (x, y - 3), (x, y + 3), color, thickness=2)
        # cv2.imshow("target", self.frame)

        return img

    def analyze(self):
        new_frame = self.pretreat()
        best_threshold = self.find_best_threshold(new_frame)
        print("best_threshold:", best_threshold)

        # kernel = np.ones((3, 3), np.uint8)
        # new_frame = cv2.erode(new_frame, kernel, iterations=3)

        new_frame = cv2.threshold(new_frame, best_threshold, 255, cv2.THRESH_BINARY)[1]
        # #cv2.imshow("binary image", new_frame)

        img = self.hough(new_frame)

        new_frame = self.add_border(new_frame)
        iris_cnt = self.find_iris_cnt(new_frame)
        self.detect_iris(iris_cnt)

        return self.frame

if __name__ == '__main__':

    webcam = cv2.VideoCapture(0)

    # 定义编解码器并创建 VideoWriter 对象
    # fourcc = cv2.VideoWriter_fourcc(*'XVID')
    # out = cv2.VideoWriter('example_1.avi',fourcc, 20.0, (64,48))

    while True:
        # 我们从网络摄像头中得到一个新的画面
        _, frame = webcam.read()

        gaze = GazeTracking(frame)
        frame = gaze.analyze()
        print(gaze.x, gaze.y)

        # 保存当前帧
        # out.write(frame)
        cv2.imshow("Demo", frame)

        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()

    # # 定义编解码器并创建 VideoWriter 对象
    # fourcc = cv2.VideoWriter_fourcc(*'XVID')
    # out = cv2.VideoWriter('example.avi', fourcc, 20.0, (64, 48))
    #
    # path = "data"
    # file_list = os.listdir(path)
    # i = 0
    # for files in file_list:
    #     frame_dir = os.path.join(path, files)
    #     frame = cv2.imread(frame_dir)
    #
    #     gaze = GazeTracking(frame)
    #     img = gaze.analyze()
    #
    #     out.write(img)
    #     i += 1
    #     img_dir = "tests/" + str(i) + ".jpg"
    #     print(img_dir)
    #     cv2.imwrite(img_dir, img)
    #     print(gaze.x, gaze.y)
    #
    # cv2.waitKey(0)

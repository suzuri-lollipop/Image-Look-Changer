import win32gui
import win32ui
import win32con
import win32api
from PIL import ImageGrab
import numpy as np
import time  # 時間計測のために追加


class win_ss:
    def __init__(self, _width, _height, _left, _top):
        # スクリーンショットの寸法を定義
        self.width = _width
        self.height = _height
        self.left = _left
        self.top = _top

    def create_ss(self):
        # デバイスコンテキストとビットマップを作成
        hwin = win32gui.GetDesktopWindow()
        hwindc = win32gui.GetWindowDC(hwin)
        srcdc = win32ui.CreateDCFromHandle(hwindc)
        memdc = srcdc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(srcdc, self.width, self.height)
        memdc.SelectObject(bmp)
        memdc.BitBlt((0, 0), (self.width, self.height), srcdc, (self.left, self.top), win32con.SRCCOPY)

        # ビットマップから画像データを取得
        signedIntsArray = bmp.GetBitmapBits(True)
        img = np.fromstring(signedIntsArray, dtype='uint8')
        img.shape = (self.height, self.width, 4)

        # リソースを解放
        srcdc.DeleteDC()
        memdc.DeleteDC()
        win32gui.ReleaseDC(hwin, hwindc)
        win32gui.DeleteObject(bmp.GetHandle())

        return img

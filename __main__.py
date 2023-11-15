import OpenGL.GL as gl
import glfw
from PIL import Image
import numpy as np
import cv2
import threading
from time import sleep, time
import sys
from queue import Queue
import win32api_scrshot


class ImageLookChanger:
    def __init__(self):
        # TODO iniで設定を複数保存できるようにする

        x = 400 # ポジションの原点x
        y = 300 # ポジションの原点y
        cols = 800 # 原点からの幅のピクセル数
        rows = 800 # 原点からの高さのピクセル数
        view_size = 1 # 表示サイズ(倍)
        self.alpha = 1.5 # コントラスト制御 (1.0 = 通常)
        self.beta = 1 # 明るさ制御 (0 = 通常)
        self.red_adjustment = 0.1 # Rの倍率
        self.green_adjustment = 1 # Gの倍率
        self.blue_adjustment = 0 # Bの倍率
        self.bin_thresh = 60.0 # 二値化の閾値
        self.gamma = 1 # ガンマの倍率
        self.window_name = "Display" # プレビューウィンドウの名前
        self.fps = 30 # プレビューのフレームレート

        # TODO 設定をレイヤーのようにできるようにする

        # プレビューウィンドウサイズの定義
        self.view_cols = int(cols * view_size)
        self.view_rows = int(rows * view_size)

        # プレビューウィンドウサイズの定義
        self.target_position = (x, y, x + cols, y + rows)

        self.capture_buffer = Queue(maxsize=5)  # キャプチャ用バッファ
        self.process_buffer = Queue(maxsize=5)  # 処理用バッファ
        self.capture_lock = threading.Lock()     # キャプチャ用ロック
        self.process_lock = threading.Lock()     # 処理用ロック

        # 一度だけフレームを処理してimshowのnullを回避
        self.winss = win32api_scrshot.win_ss(cols,rows,x,y)
        frame = self.take_screenshot()
        with self.capture_lock:    
            if not self.capture_buffer.full():
                self.capture_buffer.put(frame)

        # スレッドの作成と実行
        capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        sleep(0.5)
        process_thread = threading.Thread(target=self.image_cvt_process, daemon=True)
        view_thread = threading.Thread(target=self.image_view_process, daemon=True)
        capture_thread.start()
        process_thread.start()
        view_thread.run()

    def take_screenshot(self):
        # スクリーンショット
        try:
            shot_img = self.winss.create_ss()
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            raise e
                
        return shot_img

    def cvt_image(self, _frame):

        frame = cv2.cvtColor(_frame, cv2.COLOR_BGRA2BGR)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        frame[:, :, 0] = np.clip(frame[:, :, 0] * self.red_adjustment, 0, 255)
        frame[:, :, 1] = np.clip(frame[:, :, 1] * self.green_adjustment, 0, 255)
        frame[:, :, 2] = np.clip(frame[:, :, 2] * self.blue_adjustment, 0, 255)
        
        frame = cv2.convertScaleAbs(frame,alpha=self.alpha,beta=self.beta)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        #cv2.threshold(frame, self.bin_thresh, 255, cv2.THRESH_BINARY, frame)
        # 最終的に渡すフレームはRGBを想定
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        
        frame = cv2.convertScaleAbs(frame,alpha=self.alpha,beta=self.beta)

        inv_gamma = 1 / self.gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")

        # ルックアップテーブルを使用してガンマ補正を適用
        frame = cv2.LUT(frame, table)
        #frame = cv2.resize(frame,(int(keiryo_cols*2+0.5),int(keiryo_rows*2+0.5)))
        return frame

    def capture_process(self):
        frame_duration = 1.0 / self.fps
        last_time = time()
        while True:
            current_time = time()
            elapsed_since_last = current_time - last_time
            frame = self.take_screenshot()
            with self.capture_lock:
                if not self.capture_buffer.full():
                    self.capture_buffer.put(frame)
            # 次のフレームまでの待機時間
            if elapsed_since_last < frame_duration:
                sleep_duration = frame_duration - elapsed_since_last
                sleep(sleep_duration)

            last_time = current_time

    def image_cvt_process(self):
        while True:
            with self.capture_lock:
                if not self.capture_buffer.empty():
                    frame = self.capture_buffer.get()
                else:
                    sleep(0.01)
                    continue

            processed_frame = self.cvt_image(frame)

            with self.process_lock:
                if not self.process_buffer.full():
                    self.process_buffer.put(processed_frame)

    def image_view_process(self):

        # GLFWを初期化
        if not glfw.init():
            return

        # ウィンドウを可視化
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
        window = glfw.create_window(self.view_cols, self.view_rows, self.window_name, None, None)
        if not window:
            glfw.terminate()
            return

        # ウィンドウのサイズを固定
        glfw.set_window_size_limits(window, self.view_cols, self.view_rows, self.view_cols, self.view_rows)

        # ウィンドウが最前面に表示されるように設定
        glfw.set_window_attrib(window, glfw.FLOATING, glfw.TRUE)

        # OpenGLコンテキストを作成
        glfw.make_context_current(window)

        # 描画ループ
        while not glfw.window_should_close(window):

            # OpenGLでの画像描画
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glRasterPos2f(-1, 1)
            gl.glPixelZoom(1, -1)

            with self.process_lock:
                if not self.process_buffer.empty():
                    self.final_frame = self.process_buffer.get()
                else:
                    sleep(0.01)
                    continue
            
            self.pil_image = Image.fromarray(self.final_frame)
            self.image_data = self.pil_image.convert("RGB").tobytes()

            # 画像の描画
            try:
                gl.glDrawPixels(self.pil_image.width, self.pil_image.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, self.image_data)
            except Exception as e:
                continue

            glfw.swap_buffers(window)
            glfw.poll_events()

        # 終了処理
        glfw.destroy_window(window)
        glfw.terminate()
        sys.exit()

def main():
    im = ImageLookChanger()
    # TODO pysimpleGUIでRGB値や閾値などをリアルタイムでいじれるようにする

if __name__ == "__main__":
    main()
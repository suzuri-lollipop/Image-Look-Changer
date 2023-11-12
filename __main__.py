import OpenGL.GL as gl
import glfw
from PIL import Image
import numpy as np
import cv2
import threading
from time import sleep, time
import sys
import win32api_scrshot

class ImageLookChanger:
    def __init__(self):
        # TODO iniで設定を複数保存できるようにする
        # 処理する画面位置指定
        x = 400
        y = 400
        cols = 500
        rows = 500

        # 表示サイズ(倍)
        view_size = 1

        self.alpha = 5 # コントラスト制御 (1.0 = 通常)
        self.beta = 0 # 明るさ制御 (0 = 通常)

        self.red_adjustment = 1
        self.green_adjustment = 1
        self.blue_adjustment = 1
        self.bin_thresh = 50.0

        self.view_cols = int(cols * view_size)
        self.view_rows = int(rows * view_size)

        self.target_position = (x, y, x + cols, y + rows)
        # imshowのウィンドウの名前
        self.window_name = "Display"
        # フレームレート
        self.fps = 60
        # 一度だけフレームを処理してimshowのnullを回避
        self.winss = win32api_scrshot.win_ss(cols,rows,x,y)
        self.final_frame = self.winss.create_ss()
        # スレッドロックの定義
        self.lock = threading.Lock()
        tkvw_t = threading.Thread(target=self.image_cvt_prosess,daemon=True)
        tkvw_t.start()
        view_p = threading.Thread(target=self.image_view_prosess,daemon=True)
        view_p.run()

    def take_screenshot(self):
        # スクリーンショット
        try:
            shot_img = self.winss.create_ss()
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            raise e
                
        return shot_img

    def cvt_image(self, _frame):
         
        #frame = np.array(_frame)
        frame = _frame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        frame[:, :, 0] = np.clip(frame[:, :, 2] * self.red_adjustment, 0, 255)
        frame[:, :, 1] = np.clip(frame[:, :, 2] * self.green_adjustment, 0, 255)
        frame[:, :, 2] = np.clip(frame[:, :, 2] * self.blue_adjustment, 0, 255)
        cv2.threshold(frame, self.bin_thresh, 255, cv2.THRESH_BINARY, frame)
        frame = cv2.convertScaleAbs(frame,alpha=self.alpha,beta=self.beta)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # 最終的に渡すフレームはRGBを想定
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        frame = cv2.resize(frame, (self.view_cols, self.view_rows)) #なぜかエラーが起こる
        return frame

    def image_cvt_prosess(self):

        while True:
            start_time = time()
            frame = self.take_screenshot()
            frame = self.cvt_image(frame)
            with self.lock:
                self.final_frame = frame
            # フレームレート制御
            elapsed = time() - start_time
            wait_time = max(1.0 / self.fps - elapsed, 0)
            sleep(wait_time)
 
    def image_view_prosess(self):
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

        # FPS制御用の変数
        frame_duration = 1.0 / self.fps
        last_time = time()

        # 描画ループ
        while not glfw.window_should_close(window):

            # 現在時刻
            current_time = time()
            # 前回フレームからの経過時間
            elapsed_since_last = current_time - last_time

            # OpenGLでの画像描画
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glRasterPos2f(-1, 1)
            gl.glPixelZoom(1, -1)

            # cv2で処理された画像をOpenGLが扱える形式に変換
            with self.lock:
                frame_to_display = self.final_frame.copy()      
            pil_image = Image.fromarray(frame_to_display)
            image_data = pil_image.convert("RGB").tobytes()

            # 画像の描画
            gl.glDrawPixels(pil_image.width, pil_image.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, image_data)

            glfw.swap_buffers(window)
            glfw.poll_events()

            # 次のフレームまでの待機時間
            if elapsed_since_last < frame_duration:
                sleep_duration = frame_duration - elapsed_since_last
                sleep(sleep_duration)

            last_time = current_time

        # 終了処理
        glfw.destroy_window(window)
        glfw.terminate()
        sys.exit()

def main():
    im = ImageLookChanger()
    # TODO pysimpleGUIでRGB値や閾値などをリアルタイムでいじれるようにする

if __name__ == "__main__":
    main()
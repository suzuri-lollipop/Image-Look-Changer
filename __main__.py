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
        # 処理する画面位置指定
        x = 400
        y = 300
        cols = 800
        rows = 800

        # 表示サイズ(倍)
        view_size = 1

        self.alpha = 1.5 # コントラスト制御 (1.0 = 通常)
        self.beta = 1 # 明るさ制御 (0 = 通常)

        self.red_adjustment = 0.1
        self.green_adjustment = 1
        self.blue_adjustment = 0
        self.bin_thresh = 60.0
        self.gamma = 1

        self.view_cols = int(cols * view_size)
        self.view_rows = int(rows * view_size)

        self.target_position = (x, y, x + cols, y + rows)
        # imshowのウィンドウの名前
        self.window_name = "Display"
        # フレームレート
        self.fps = 90

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
        #self.final_frame = self.winss.create_ss()
        #frame_to_display = cv2.resize(self.final_frame,(self.view_cols, self.view_rows))
        #frame_to_display = cv2.cvtColor(frame_to_display, cv2.COLOR_BGRA2RGB)
        #self.pil_image = Image.fromarray(frame_to_display)
        #self.image_data = self.pil_image.convert("RGB").tobytes()
        # スレッドロックの定義
        #self.lock = threading.Lock()
              # スレッドの作成と実行
        capture_thread = threading.Thread(target=self.capture_process, daemon=True)
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
         
        #frame = np.array(_frame)

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

        # FPS制御用の変数
        #frame_duration = 1.0 / self.fps
        #last_time = time()

        # 描画ループ
        while not glfw.window_should_close(window):

            # 現在時刻
            #current_time = time()
            # 前回フレームからの経過時間
            #elapsed_since_last = current_time - last_time

            # OpenGLでの画像描画
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glRasterPos2f(-1, 1)
            gl.glPixelZoom(1, -1)

            # cv2で処理された画像をOpenGLが扱える形式に変換

            #frame_to_display = self.final_frame.copy()
            #frame = cv2.resize(frame_to_display,(self.view_cols,self.view_rows))          
            with self.process_lock:
                if not self.process_buffer.empty():
                    self.final_frame = self.process_buffer.get()
            
            self.pil_image = Image.fromarray(self.final_frame)
            self.image_data = self.pil_image.convert("RGB").tobytes()

            # 画像の描画
            gl.glDrawPixels(self.pil_image.width, self.pil_image.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, self.image_data)

            glfw.swap_buffers(window)
            glfw.poll_events()

            # 次のフレームまでの待機時間
            #if elapsed_since_last < frame_duration:
            #    sleep_duration = frame_duration - elapsed_since_last
            #    sleep(sleep_duration)

            #last_time = current_time

        # 終了処理
        glfw.destroy_window(window)
        glfw.terminate()
        sys.exit()

def main():
    im = ImageLookChanger()
    # TODO pysimpleGUIでRGB値や閾値などをリアルタイムでいじれるようにする

if __name__ == "__main__":
    main()
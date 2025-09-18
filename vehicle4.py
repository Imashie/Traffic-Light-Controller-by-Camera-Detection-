import cv2
import numpy as np
import os
import threading
import queue
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def vehicle_counter(video_path, window_name, count_queue, stop_event):
    logging.info(f"{window_name} - Starting vehicle counter")
    if not os.path.exists(video_path):
        logging.error(f"{window_name} - Video file not found at: {video_path}")
        count_queue.put((window_name, None, 0))
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error(f"{window_name} - Could not open video file: {video_path}")
        count_queue.put((window_name, None, 0))
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logging.info(f"{window_name} - Video properties: {width}x{height}, FPS: {fps}, Total frames: {frame_count}")

    min_width_rect = 80
    min_height_rect = 80
    count_line_position = 550
    algo = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    def center_handle(x, y, w, h):
        x1 = int(w / 2)
        y1 = int(h / 2)
        cx = x + x1
        cy = y + y1
        return cx, cy

    recently_counted = []
    offset = 6
    counter = 0
    cooldown_frames = 15
    frame_idx = 0

    while not stop_event.is_set():
        ret, frame1 = cap.read()
        if not ret or frame1 is None or frame1.size == 0:
            logging.info(f"{window_name} - End of video or error reading frame")
            break

        frame_idx += 1
        grey = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(grey, (3, 3), 5)
        img_sub = algo.apply(blur)
        dilat = cv2.dilate(img_sub, np.ones((5, 5)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilatada = cv2.morphologyEx(dilat, cv2.MORPH_CLOSE, kernel)
        dilatada = cv2.morphologyEx(dilatada, cv2.MORPH_CLOSE, kernel)
        counterShape, _ = cv2.findContours(dilatada, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cv2.line(frame1, (25, count_line_position), (1200, count_line_position), (255, 127, 0), 3)

        centers = []
        for c in counterShape:
            (x, y, w, h) = cv2.boundingRect(c)
            if w >= min_width_rect and h >= min_height_rect:
                center = center_handle(x, y, w, h)
                centers.append(center)
                cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(frame1, center, 4, (0, 0, 255), -1)

        for center in centers:
            cx, cy = center
            if abs(cy - count_line_position) < offset:
                already_counted = False
                for prev_center, prev_frame in recently_counted:
                    if abs(cx - prev_center[0]) < 30 and abs(cy - prev_center[1]) < 30 and (frame_idx - prev_frame) < cooldown_frames:
                        already_counted = True
                        break
                if not already_counted:
                    counter += 1
                    recently_counted.append((center, frame_idx))
                    cv2.line(frame1, (25, count_line_position), (1200, count_line_position), (0, 127, 255), 3)
                    logging.info(f"{window_name} - Vehicle Counter: {counter}")

        recently_counted = [(c, f) for c, f in recently_counted if (frame_idx - f) < cooldown_frames]

        cv2.putText(frame1, f"{window_name} VEHICLE COUNTER: {counter}", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
        cv2.putText(frame1, "Press 'Z' to exit", (50, height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        aspect_ratio = width / height
        new_width = 640
        new_height = int(new_width / aspect_ratio)
        display_frame = cv2.resize(frame1, (new_width, new_height))

        count_queue.put((window_name, display_frame, counter))

        # Small sleep to prevent tight loop and ensure stop_event is checked
        time.sleep(0.001)

    cap.release()
    count_queue.put((window_name, None, counter))
    logging.info(f"{window_name} - Final vehicle count: {counter}")

def write_counts_table(final_counts, output_dir="C:\\Users\\User\\Desktop\\_sumo_", filename="countfile.py"):
    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            f.write('"""\n')
            f.write("Lane        | Vehicle Count\n")
            f.write("------------|--------------\n")
            for lane, count in final_counts.items():
                f.write(f"{lane:<12}| {count}\n")
            f.write('"""\n')
            f.write("\nlane_counts = {\n")
            for lane, count in final_counts.items():
                f.write(f"    '{lane}': {count},\n")
            f.write("}\n")
        logging.info(f"Successfully wrote counts to {filepath}")
    except Exception as e:
        logging.error(f"Error writing to {filepath}: {e}")

def display_frames(count_queue, lane_list, stop_event):
    windows = set(lane_list)
    final_counts = {lane: 0 for lane in lane_list}
    logging.info("Starting display thread")
    while windows:
        try:
            window_name, frame, counter = count_queue.get(timeout=0.1)
            if frame is None:
                if window_name in windows:
                    cv2.destroyWindow(window_name)
                    windows.remove(window_name)
                    final_counts[window_name] = counter
                    logging.info(f"{window_name} - Window closed, count: {counter}")
                continue
            final_counts[window_name] = counter
            if window_name not in windows:
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('z') or key == ord('Z'):
                logging.info("Z key pressed - stopping all execution")
                stop_event.set()
                # Clear queue to prevent processing stale frames
                while not count_queue.empty():
                    try:
                        count_queue.get_nowait()
                    except queue.Empty:
                        break
                for wn in list(windows):
                    cv2.destroyWindow(wn)
                    windows.remove(wn)
                write_counts_table(final_counts)
                logging.info("Counts saved to countfile.py")
                break
        except queue.Empty:
            if stop_event.is_set():
                for wn in list(windows):
                    cv2.destroyWindow(wn)
                    windows.remove(wn)
                write_counts_table(final_counts)
                logging.info("Counts saved to countfile.py (stop event)")
                break
    cv2.destroyAllWindows()
    logging.info("Final vehicle counts per lane:")
    for lane, count in final_counts.items():
        logging.info(f"{lane}: {count}")

def main():
    video_paths = [
        r'C:\Users\User\Desktop\_sumo_\Video.mp4',
        r'C:\Users\User\Desktop\_sumo_\Video2.mp4',
        r'C:\Users\User\Desktop\_sumo_\Video3.mp4'
    ]
    window_names = ["Lane 1", "Lane 2", "Lane 3"]

    count_queue = queue.Queue()
    stop_event = threading.Event()
    threads = []
    for path, name in zip(video_paths, window_names):
        t = threading.Thread(target=vehicle_counter, args=(path, name, count_queue, stop_event))
        t.start()
        threads.append(t)

    display_thread = threading.Thread(target=display_frames, args=(count_queue, window_names, stop_event))
    display_thread.start()

    for t in threads:
        t.join()
    display_thread.join()
    logging.info("All threads terminated")

if __name__ == "__main__":
    main()
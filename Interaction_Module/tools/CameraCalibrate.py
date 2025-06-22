# camera_calibration.py

import cv2
import numpy as np

# -------------- User Settings --------------
# Number of inner corners per chessboard row and column (columns, rows)
CHESSBOARD_SIZE = (9, 6)  # for an 8 x 7 inner corner grid
SQUARE_SIZE = 1.9  # size of one chessboard square in centimeters
# -------------------------------------------

# Prepare object points based on the specified chessboard dimensions.
# e.g., (0,0,0), (square_size, 0, 0), ..., ((cols-1)*square_size, (rows-1)*square_size, 0)
objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE

# Arrays to store object points and image points from all calibration images.
objpoints = []  # 3D points in real world space
imgpoints = []  # 2D points in image plane.

cap = cv2.VideoCapture(0)
print("Press SPACE to capture a frame when the chessboard is visible. Press 'q' to finish.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Find the chessboard corners
    found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

    if found:
        # Increase accuracy by refining the corner positions
        criteria = (cv2.TermCriteria_EPS + cv2.TermCriteria_MAX_ITER, 30, 0.001)
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        cv2.drawChessboardCorners(frame, CHESSBOARD_SIZE, corners2, found)

    cv2.putText(frame, "Press SPACE to capture, 'q' to exit.", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 255, 0), 2)
    cv2.imshow('Camera Calibration', frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord(' '):
        if found:
            print("Chessboard found, capturing corners...")
            objpoints.append(objp)
            imgpoints.append(corners2)
        else:
            print("Chessboard not detected, try again.")
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

if len(objpoints) < 5:
    print("Not enough data collected for calibration. Capture more images and try again.")
else:
    # Perform camera calibration to obtain intrinsic matrix and distortion coefficients.
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
    print("Calibration successful!")
    print("Camera Matrix:\n", mtx)
    print("Distortion Coefficients:\n", dist)

    # Save the calibration data to a file
    np.savez("calibration.npz", camera_matrix=mtx, dist_coefficients=dist)
    print("Calibration data saved to 'calibration.npz'.")

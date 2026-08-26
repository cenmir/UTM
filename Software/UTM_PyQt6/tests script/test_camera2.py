from pypylon import pylon
import cv2

# Grab frame
tl_factory = pylon.TlFactory.GetInstance()
camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
camera.Open()
camera.ExposureTime.Value = 5000
camera.PixelFormat.Value = "Mono8"
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
img = None
if grab_result.GrabSucceeded():
    img = grab_result.Array
    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    print(f"Frame shape: {img.shape}")

grab_result.Release()
camera.StopGrabbing()
camera.Close()

# Click to get coordinates
scale_x = img.shape[1] / 800
scale_y = img.shape[0] / 1000

def click_scaled(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        real_x = int(x * scale_x)
        real_y = int(y * scale_y)
        print(f"Clicked: x={real_x}, y={real_y}")
        cv2.circle(display, (x, y), 8, 128, -1)
        cv2.imshow("Click on both dots then press any key", display)

display = cv2.resize(img, (800, 1000))
cv2.imshow("Click on both dots then press any key", display)
cv2.setMouseCallback("Click on both dots then press any key", click_scaled)
print("Click on each dot, then press any key to exit")
cv2.waitKey(0)
cv2.destroyAllWindows()
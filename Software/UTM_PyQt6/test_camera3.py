from pypylon import pylon
import cv2

tl_factory = pylon.TlFactory.GetInstance()
camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
camera.Open()

# Reset ROI to full sensor first
camera.Width.Value   = camera.Width.Max
camera.Height.Value  = camera.Height.Max
camera.OffsetX.Value = 0
camera.OffsetY.Value = 0

camera.ExposureTime.Value = 50000
camera.PixelFormat.Value = "Mono8"
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
img = None
if grab_result.GrabSucceeded():
    img = grab_result.Array.copy()
    print(f"Raw sensor shape: {img.shape}")

grab_result.Release()
camera.StopGrabbing()
camera.Close()

# Show and click
scale_x = img.shape[1] / 800
scale_y = img.shape[0] / 600

display = cv2.resize(img, (800, 600))

def click_scaled(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        real_x = int(x * scale_x)
        real_y = int(y * scale_y)
        print(f"Clicked: x={real_x}, y={real_y}")
        cv2.circle(display, (x, y), 8, 128, -1)
        cv2.imshow("Click both dots then press any key", display)

cv2.imshow("Click both dots then press any key", display)
cv2.setMouseCallback("Click both dots then press any key", click_scaled)
print("Click each dot then press any key to exit")
cv2.waitKey(0)
cv2.destroyAllWindows()
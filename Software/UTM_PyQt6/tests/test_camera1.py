from pypylon import pylon
import cv2

tl_factory = pylon.TlFactory.GetInstance()
camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
camera.Open()

# Reset first
camera.Width.Value   = camera.Width.Max
camera.Height.Value  = camera.Height.Max
camera.OffsetX.Value = 0
camera.OffsetY.Value = 0

# Apply new ROI
camera.Width.Value   = 1600
camera.Height.Value  = 200
camera.OffsetX.Value = 0
camera.OffsetY.Value = 1800

camera.ExposureTime.Value = 50000  # Original value — do not change
camera.PixelFormat.Value = "Mono8"
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
if grab_result.GrabSucceeded():
    img = grab_result.Array.copy()
    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    cv2.imwrite("output/test_images/sample_image.png", img)
    print(f"ROI frame shape: {img.shape}")

grab_result.Release()
camera.StopGrabbing()
camera.Close()
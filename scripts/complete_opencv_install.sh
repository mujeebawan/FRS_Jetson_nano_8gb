#!/bin/bash
# Script to complete OpenCV installation after build finishes
# Run this after the build completes

echo "Checking OpenCV build status..."

BUILD_LOG="/home/tempuser/Downloads/frs/docs/opencv_build.log"
BUILD_DIR="$HOME/opencv/build"

# Check if build is complete
if tail -5 "$BUILD_LOG" | grep -q "100%"; then
    echo "OpenCV build completed successfully!"

    echo "Installing OpenCV..."
    cd "$BUILD_DIR"
    sudo make install
    sudo ldconfig

    echo "Verifying installation..."
    python3 -c "
import cv2
print(f'OpenCV Version: {cv2.__version__}')
cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
print(f'CUDA Devices: {cuda_count}')
if cuda_count > 0:
    print('SUCCESS: OpenCV with CUDA is working!')
else:
    print('WARNING: No CUDA devices found')
"
else
    # Show current progress
    PROGRESS=$(tail -1 "$BUILD_LOG" | grep -oP '\[\s*\d+%\]' | tail -1)
    echo "Build still in progress: $PROGRESS"
    echo "Run 'tail -f $BUILD_LOG' to watch progress"
    echo "Re-run this script after build completes"
fi

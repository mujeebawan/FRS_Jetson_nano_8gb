#!/bin/bash
#
# Install FRS as systemd services for auto-start on boot
#

set -e

echo "Installing Face Recognition System services..."
echo ""

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log/frs
sudo chown tempuser:Mujeeb /var/log/frs

# Copy service files
echo "Installing systemd services..."
sudo cp /home/tempuser/Downloads/frs/frs.service /etc/systemd/system/frs.service
sudo cp /home/tempuser/Downloads/frs/frs-frontend.service /etc/systemd/system/frs-frontend.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable services (auto-start on boot)
echo "Enabling services..."
sudo systemctl enable frs.service
sudo systemctl enable frs-frontend.service

echo ""
echo "============================================"
echo "  FRS Services Installed Successfully!"
echo "============================================"
echo ""
echo "Services:"
echo "  - frs.service (Backend API + Face Recognition)"
echo "  - frs-frontend.service (Web UI)"
echo ""
echo "Commands:"
echo "  Start all:    sudo systemctl start frs frs-frontend"
echo "  Stop all:     sudo systemctl stop frs frs-frontend"
echo "  Restart all:  sudo systemctl restart frs frs-frontend"
echo "  Status:       sudo systemctl status frs frs-frontend"
echo ""
echo "Logs:"
echo "  Backend:  sudo tail -f /var/log/frs/backend.log"
echo "  Frontend: sudo tail -f /var/log/frs/frontend.log"
echo ""
echo "Access:"
echo "  Frontend: http://$(hostname -I | awk '{print $1}'):5173"
echo "  API:      http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Both services will auto-start on boot."

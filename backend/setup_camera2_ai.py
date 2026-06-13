"""
Setup script: Enable AI detection for all Camera 2 devices (5 coops A-E)

Steps:
1. Update database: set stream_url, stream_enabled=True, frame_skip=5
2. Restart the server so StreamManager picks up the changes
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import config
from models import db, Device, CoopDevice, Coop


def create_app():
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)
    return app


def setup_camera2_ai():
    app = create_app()
    with app.app_context():
        db.create_all()

        print("=" * 60)
        print("  SETUP AI DETECTION FOR ALL CAMERA 2 DEVICES")
        print("=" * 60)

        cameras = Device.query.filter(
            Device.type == 'camera',
            Device.deleted == False,
            Device.name.like('%Camera 2%')
        ).order_by(Device.id.asc()).all()

        if not cameras:
            print("  [ERROR] No Camera 2 devices found!")
            return

        print(f"\n  Found {len(cameras)} Camera 2 devices:\n")

        updated_count = 0
        for cam in cameras:
            coop_device = CoopDevice.query.filter_by(
                device_id=cam.id, deleted=False
            ).first()
            coop = Coop.query.get(coop_device.coop_id) if coop_device else None
            coop_name = coop.name if coop else 'Unknown'

            old_url = cam.stream_url
            old_enabled = cam.stream_enabled
            old_skip = cam.frame_skip

            # Set stream_url (mock RTSP URL for testing)
            # In production, replace with actual RTSP URL
            mock_url = f'rtsp://camera-{cam.id}.local:8554/stream'
            cam.stream_url = mock_url
            cam.stream_enabled = True
            cam.frame_skip = 5

            db.session.flush()

            print(f"    [{'OK' if old_enabled != True or old_url != mock_url else 'SKIP'}] {cam.name}")
            print(f"         ID:          {cam.id}")
            print(f"         Coop:        {coop_name}")
            print(f"         Stream URL:  {old_url or 'None'} -> {mock_url}")
            print(f"         Enabled:     {old_enabled} -> True")
            print(f"         Frame Skip:  {old_skip} -> 5")
            print()

            updated_count += 1

        db.session.commit()

        print(f"  Updated {updated_count}/{len(cameras)} cameras successfully!")
        print()

        # Verify
        print("-" * 60)
        print("  VERIFICATION")
        print("-" * 60)
        verify_cameras = Device.query.filter(
            Device.type == 'camera',
            Device.deleted == False,
            Device.name.like('%Camera 2%')
        ).order_by(Device.id.asc()).all()

        for cam in verify_cameras:
            coop_device = CoopDevice.query.filter_by(
                device_id=cam.id, deleted=False
            ).first()
            coop = Coop.query.get(coop_device.coop_id) if coop_device else None
            coop_name = coop.name if coop else 'Unknown'
            status = '✓ READY' if cam.stream_enabled and cam.stream_url else '✗ NOT READY'
            print(f"    [{status}] {cam.name} ({coop_name})")
            print(f"         URL: {cam.stream_url}")
            print(f"         Enabled: {cam.stream_enabled}")
        print()

        print("  ✅ All Camera 2 devices are now configured for AI detection!")
        print()
        print("  NEXT STEPS:")
        print("  1. Start the server: python run.py")
        print("  2. The StreamManager will auto-register and start all 5 cameras")
        print("  3. Verify status: GET /api/camera/detection/status-all")
        print("  4. Check live stream: GET /api/camera/<id>/live.mjpeg")
        print("  5. View detection results via WebSocket")
        print()
        print("  To use REAL RTSP cameras:")
        print("  - Edit this script and replace mock_url with actual RTSP URL per coop")
        print("  - Or use: PUT /api/camera/<id>/stream-config")
        print("  - Set stream_manager.use_mock_workers = False in stream_manager.py")
        print()


if __name__ == '__main__':
    setup_camera2_ai()

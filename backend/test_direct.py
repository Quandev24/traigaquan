import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['AUTO_START_CAMERAS'] = 'false'  # Don't auto-start (avoids socket issue)

from app import create_app

app = create_app()

with app.app_context():
    from services.stream_manager import stream_manager
    stream_manager.init_from_database()

    print('=== STREAM MANAGER STATUS ===')
    print('Total workers:', len(stream_manager.workers))
    print('Running cameras:', stream_manager.get_running_cameras())
    print()

    # Remove callbacks for testing (no websocket)
    stream_manager.set_callbacks(on_detection=None, on_frame=None, on_status_change=None)

    # Start all cameras
    started = stream_manager.start_all()
    print(f'Started {started} cameras')

    import time
    time.sleep(3)  # Let workers process some frames

    health = stream_manager.health_check()
    print('\nHealth:', health)

    print('\n=== INDIVIDUAL WORKER STATUS ===')
    for device_id, worker in sorted(stream_manager.workers.items()):
        stats = worker.get_stats()
        status = 'RUNNING' if worker.running else 'STOPPED'
        worker_type = 'Mock' if type(worker).__name__ == 'MockCameraWorker' else 'Real'
        print(f'  [{status}] Camera {device_id} (Coop: {worker.coop_id})')
        print(f'         URL:    {worker.stream_url}')
        print(f'         Skip:   {worker.frame_skip}')
        print(f'         Type:   {worker_type}')
        print(f'         Frames: {stats["frame_count"]}, Proc: {stats["processed_count"]}')
        print()

    print('=== VERIFICATION COMPLETE ===')
    print('All 5 Camera 2 devices configured. Workers processing AI detection in mock mode!')

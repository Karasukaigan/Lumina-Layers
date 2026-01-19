"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          LUMINA STUDIO v1.3                                   ║
║                    Multi-Material 3D Print Color System                       ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Author: [MIN]                                                                ║
║  License: CC BY-NC-SA 4.0                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Main Entry Point
"""

import os
import sys
import time
import threading
import webbrowser
import gradio as gr     # type:ignore
from ui.layout import create_app
from core.tray import LuminaTray
from ui.styles import CUSTOM_CSS

PORT = 7860

def start_browser():
    """Launch the default web browser after a short delay."""
    time.sleep(2)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__ == "__main__":
    # Launch Gradio App FIRST (before system tray to avoid conflicts)
    print(f"✨ Lumina Studio is running on http://127.0.0.1:{PORT}")
    app = create_app()

    try:
        app.launch(
            inbrowser=False,
            server_name="127.0.0.1",
            server_port=PORT,
            show_error=True,
            prevent_thread_lock=True,
            favicon_path="icon.ico" if os.path.exists("icon.ico") else None,
            css=CUSTOM_CSS, 
            theme=gr.themes.Soft()
        )
    except Exception as e:
        raise
    except BaseException as e:
        raise

    # Start System Tray AFTER Gradio is launched
    # On macOS, pystray can cause trace trap errors when running alongside Gradio
    # Disable system tray on macOS to avoid crashes
    if sys.platform != "darwin":  # Only enable on non-macOS systems
        print("🚀 Starting System Tray...")
        try:
            tray = LuminaTray(port=PORT)
            tray.run()
        except Exception as e:
            print(f"⚠️ Warning: System tray failed to start: {e}")
    else:
        print("ℹ️ System tray disabled on macOS to avoid compatibility issues")

    # Start Browser Thread
    threading.Thread(target=start_browser, daemon=True).start()

    # Keep Main Thread Alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        os._exit(0)

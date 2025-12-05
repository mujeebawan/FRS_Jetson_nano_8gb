#!/usr/bin/env python3
"""
Dahua Camera Control Panel
Left: Live RTSP stream via OpenCV
Right: PTZ controls from camera web interface
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, WebKit2, Gdk, GLib, GdkPixbuf
import cv2
import threading
import numpy as np

# Camera configuration
DEFAULT_CAMERA_IP = "10.1.1.68"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "system123"
DEFAULT_RTSP_PORT = "554"
DEFAULT_CHANNEL = "1"
DEFAULT_SUBTYPE = "1"  # 0=main stream (1080p), 1=sub stream (lower res, faster)


class DahuaCameraPanel(Gtk.Window):
    """Camera control panel with live stream and PTZ controls."""

    def __init__(self):
        super().__init__(title="Camera Live View + PTZ Control")
        self.set_default_size(1400, 800)

        # Camera settings
        self.camera_ip = DEFAULT_CAMERA_IP
        self.username = DEFAULT_USERNAME
        self.password = DEFAULT_PASSWORD
        self.logged_in = False

        # Stream control
        self.cap = None
        self.stream_running = False
        self.stream_thread = None
        self.current_frame = None
        self.frame_lock = threading.Lock()

        # Apply dark theme
        self.apply_dark_theme()

        # Build UI
        self.build_ui()

        # Handle close
        self.connect("delete-event", self.on_delete)

    def apply_dark_theme(self):
        css = b"""
        window {
            background-color: #1a1a2e;
        }
        label {
            color: #eeeeee;
        }
        entry {
            background-color: #2d2d44;
            color: #eeeeee;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 5px;
        }
        button {
            background: #3d5a80;
            color: #ffffff;
            border: 1px solid #4a6fa5;
            border-radius: 5px;
            padding: 8px 16px;
            font-weight: bold;
        }
        button:hover {
            background: #4a6fa5;
        }
        button:active {
            background: #5c7cba;
        }
        .status-connected {
            color: #2ecc71;
        }
        .status-error {
            color: #e74c3c;
        }
        .stream-frame {
            background-color: #000000;
        }
        .ptz-frame {
            background-color: #1a1a2e;
        }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_ui(self):
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # Header bar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.set_margin_start(10)
        header.set_margin_end(10)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<b>Live View + PTZ Control</b>")
        header.pack_start(title_label, False, False, 0)

        # Separator
        header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 10)

        # Refresh PTZ button
        refresh_btn = Gtk.Button(label="Refresh PTZ")
        refresh_btn.connect("clicked", self.on_refresh_ptz)
        header.pack_start(refresh_btn, False, False, 0)

        # Restart stream button
        restart_stream_btn = Gtk.Button(label="Restart Stream")
        restart_stream_btn.connect("clicked", self.on_restart_stream)
        header.pack_start(restart_stream_btn, False, False, 0)

        # Spacer
        header.pack_start(Gtk.Label(label=""), True, True, 0)

        # Stream status
        self.stream_status = Gtk.Label(label="Stream: Starting...")
        header.pack_end(self.stream_status, False, False, 10)

        # PTZ status
        self.ptz_status = Gtk.Label(label="PTZ: Connecting...")
        header.pack_end(self.ptz_status, False, False, 10)

        main_box.pack_start(header, False, False, 0)
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Horizontal paned for stream (left 75%) and right panel (25%)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(self.paned, True, True, 0)

        # LEFT SIDE: Video stream area (75%)
        stream_frame = Gtk.Frame()
        stream_frame.get_style_context().add_class("stream-frame")

        # Image widget for video display
        self.video_image = Gtk.Image()
        self.video_image.set_hexpand(True)
        self.video_image.set_vexpand(True)

        stream_frame.add(self.video_image)
        self.paned.pack1(stream_frame, resize=False, shrink=False)

        # RIGHT SIDE: Vertical split (25% of window, split into top/bottom)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)

        # TOP RIGHT: PTZ controls (WebKit)
        ptz_frame = Gtk.Frame()
        ptz_frame.get_style_context().add_class("ptz-frame")

        self.webview = WebKit2.WebView()
        self.setup_webview()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.webview)

        ptz_frame.add(scrolled)
        self.right_paned.pack1(ptz_frame, resize=False, shrink=False)

        # BOTTOM RIGHT: Future panel (placeholder for now)
        bottom_frame = Gtk.Frame()
        bottom_frame.get_style_context().add_class("ptz-frame")

        bottom_label = Gtk.Label(label="Reserved Panel")
        bottom_label.set_opacity(0.5)
        bottom_frame.add(bottom_label)
        self.right_paned.pack2(bottom_frame, resize=False, shrink=False)

        self.paned.pack2(self.right_paned, resize=False, shrink=False)

        # Set initial positions after window is realized
        self.connect("size-allocate", self.on_size_allocate_once)

        # Start stream and PTZ after window is shown
        GLib.timeout_add(500, self.start_stream)
        GLib.timeout_add(500, self.auto_login_ptz)

    def on_size_allocate_once(self, widget, allocation):
        """Set pane positions based on window size (called once)."""
        # Disconnect so it only runs once
        self.disconnect_by_func(self.on_size_allocate_once)

        # Stream takes 80%, right panel takes 20%
        self.paned.set_position(int(allocation.width * 0.80))

        # Right panel: PTZ 55% (11/20), Reserved 45% (9/20)
        right_height = allocation.height - 50  # account for header
        self.right_paned.set_position(int(right_height * 0.55))

    def setup_webview(self):
        """Configure WebView for PTZ controls."""
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_plugins(True)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_allow_modal_dialogs(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_mediasource(True)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_enable_webgl(True)
        settings.set_user_agent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.webview.connect("authenticate", self.on_authenticate)
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("load-failed", self.on_load_failed)

    def get_rtsp_url(self):
        """Build RTSP URL for Dahua camera."""
        return f"rtsp://{self.username}:{self.password}@{self.camera_ip}:{DEFAULT_RTSP_PORT}/cam/realmonitor?channel={DEFAULT_CHANNEL}&subtype={DEFAULT_SUBTYPE}"

    def start_stream(self):
        """Start the RTSP video stream."""
        if self.stream_running:
            return False

        self.stream_running = True
        self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.stream_thread.start()

        # Start UI update timer
        GLib.timeout_add(33, self._update_video_display)  # ~30 FPS

        return False

    def _stream_loop(self):
        """Background thread for capturing video frames."""
        rtsp_url = self.get_rtsp_url()

        while self.stream_running:
            try:
                # Open capture
                self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not self.cap.isOpened():
                    GLib.idle_add(self._update_stream_status, "Stream: Connection failed", True)
                    break

                GLib.idle_add(self._update_stream_status, "Stream: Playing", False)

                while self.stream_running and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        # Convert BGR to RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        with self.frame_lock:
                            self.current_frame = frame_rgb
                    else:
                        # Lost connection, try to reconnect
                        GLib.idle_add(self._update_stream_status, "Stream: Reconnecting...", True)
                        break

            except Exception as e:
                print(f"Stream error: {e}")
                GLib.idle_add(self._update_stream_status, f"Stream: Error", True)

            finally:
                if self.cap:
                    self.cap.release()
                    self.cap = None

            # Wait before reconnecting
            if self.stream_running:
                import time
                time.sleep(2)

    def _update_stream_status(self, text, is_error):
        """Update stream status label (called from main thread)."""
        self.stream_status.set_text(text)
        if is_error:
            self.stream_status.get_style_context().remove_class("status-connected")
            self.stream_status.get_style_context().add_class("status-error")
        else:
            self.stream_status.get_style_context().remove_class("status-error")
            self.stream_status.get_style_context().add_class("status-connected")
        return False

    def _update_video_display(self):
        """Update the video display widget (called from main thread)."""
        if not self.stream_running:
            return False

        with self.frame_lock:
            frame = self.current_frame

        if frame is not None:
            try:
                # Get display area size
                allocation = self.video_image.get_allocation()
                disp_w = max(allocation.width, 640)
                disp_h = max(allocation.height, 480)

                # Calculate aspect-ratio-preserving size
                h, w = frame.shape[:2]
                scale = min(disp_w / w, disp_h / h)
                new_w = int(w * scale)
                new_h = int(h * scale)

                # Resize frame
                resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

                # Convert to GdkPixbuf
                h, w, c = resized.shape
                pixbuf = GdkPixbuf.Pixbuf.new_from_data(
                    resized.tobytes(),
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    w, h,
                    w * c
                )
                self.video_image.set_from_pixbuf(pixbuf)
            except Exception as e:
                print(f"Display error: {e}")

        return self.stream_running

    def auto_login_ptz(self):
        """Load the camera PTZ page."""
        url = f"http://{self.camera_ip}/"
        self.webview.load_uri(url)
        return False

    def inject_auto_login_script(self):
        """Inject JavaScript to auto-fill and submit login form for Dahua cameras."""
        script = f"""
        (function() {{
            console.log('Auto-login script running...');

            // Try multiple selectors for Dahua cameras
            var userSelectors = [
                'input[name="username"]', 'input[id="username"]',
                'input[name="userName"]', 'input[id="userName"]',
                'input[name="user"]', 'input[id="user"]',
                '#loginUser', '.login-user input',
                'input[type="text"]:first-of-type'
            ];

            var passSelectors = [
                'input[name="password"]', 'input[id="password"]',
                'input[name="pwd"]', 'input[id="pwd"]',
                '#loginPwd', '.login-pwd input',
                'input[type="password"]'
            ];

            var btnSelectors = [
                'button[type="submit"]', 'input[type="submit"]',
                '.login-btn', '#login-btn', '#loginBtn',
                'button.btn-login', '.btn-primary',
                'a.login', 'div.login-btn', 'span.login-btn',
                'button:contains("Login")', 'button:contains("login")'
            ];

            var userInput = null, passInput = null, loginBtn = null;

            // Find username field
            for (var i = 0; i < userSelectors.length && !userInput; i++) {{
                userInput = document.querySelector(userSelectors[i]);
            }}

            // Find password field
            for (var i = 0; i < passSelectors.length && !passInput; i++) {{
                passInput = document.querySelector(passSelectors[i]);
            }}

            // Find login button
            for (var i = 0; i < btnSelectors.length && !loginBtn; i++) {{
                loginBtn = document.querySelector(btnSelectors[i]);
            }}

            // Also try finding button by text content
            if (!loginBtn) {{
                var allBtns = document.querySelectorAll('button, input[type="button"], a.btn, div[onclick]');
                for (var i = 0; i < allBtns.length; i++) {{
                    var txt = allBtns[i].textContent || allBtns[i].value || '';
                    if (txt.toLowerCase().indexOf('login') !== -1 || txt.toLowerCase().indexOf('sign') !== -1) {{
                        loginBtn = allBtns[i];
                        break;
                    }}
                }}
            }}

            console.log('Found user:', !!userInput, 'pass:', !!passInput, 'btn:', !!loginBtn);

            if (userInput && passInput) {{
                // Set values using multiple methods for compatibility
                userInput.value = '{self.username}';
                passInput.value = '{self.password}';

                // Trigger various events to ensure frameworks pick up changes
                ['input', 'change', 'keyup', 'blur'].forEach(function(evt) {{
                    userInput.dispatchEvent(new Event(evt, {{ bubbles: true }}));
                    passInput.dispatchEvent(new Event(evt, {{ bubbles: true }}));
                }});

                // Also try setting via native setter (for React/Vue)
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (nativeInputValueSetter) {{
                    nativeInputValueSetter.call(userInput, '{self.username}');
                    nativeInputValueSetter.call(passInput, '{self.password}');
                    userInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    passInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}

                // Click login button after a short delay
                setTimeout(function() {{
                    if (loginBtn) {{
                        console.log('Clicking login button...');
                        loginBtn.click();
                    }}
                    // Also try form submit
                    var form = document.querySelector('form');
                    if (form && !loginBtn) {{
                        form.submit();
                    }}
                }}, 800);
            }}

            // Try Dahua-specific global login functions
            setTimeout(function() {{
                if (typeof loginManager !== 'undefined' && loginManager.login) {{
                    loginManager.login('{self.username}', '{self.password}');
                }}
                if (typeof g_username !== 'undefined') {{
                    g_username = '{self.username}';
                    g_password = '{self.password}';
                }}
                if (typeof doLogin === 'function') {{
                    doLogin();
                }}
                if (typeof Login === 'function') {{
                    Login('{self.username}', '{self.password}');
                }}
            }}, 500);
        }})();
        """
        self.webview.run_javascript(script, None, None, None)

    def inject_ptz_only_style(self):
        """Inject CSS/JS to show only PTZ controls."""
        script = """
        (function() {
            var style = document.createElement('style');
            style.textContent = `
                /* Hide video area */
                .video-area, .video-container, .video-box, .live-video,
                #video, #videoContainer, #videoBox, .video-wrap,
                .player-container, .player-wrap, .video-player,
                .main-video, #mainVideo, .stream-container,
                .left-panel, .video-panel, #liveVideo,
                .dhweb-live-video, .dhweb-video-box,
                .live-left, .preview-area, .video-preview {
                    display: none !important;
                }

                /* Hide header/nav */
                .header, .nav-bar, .top-bar, #header,
                .menu-bar, .main-nav, .side-nav {
                    display: none !important;
                }

                /* Make PTZ controls visible and fill space */
                .ptz-panel, .ptz-container, .ptz-control, .control-panel,
                .right-panel, #ptzPanel, #ptzControl, .ptz-wrap,
                .dhweb-ptz, .dhweb-control-panel, .operation-panel,
                .live-right, .control-area, .ptz-area {
                    position: fixed !important;
                    left: 0 !important;
                    top: 0 !important;
                    width: 100% !important;
                    height: 100% !important;
                    margin: 0 !important;
                    z-index: 9999 !important;
                    background: #1a1a2e !important;
                    overflow: auto !important;
                }

                body {
                    overflow: hidden !important;
                    background: #1a1a2e !important;
                }

                .split-bar, .resizer, .divider {
                    display: none !important;
                }
            `;
            document.head.appendChild(style);
        })();
        """
        self.webview.run_javascript(script, None, None, None)

    def on_refresh_ptz(self, widget):
        """Refresh PTZ panel."""
        self.webview.reload()

    def on_restart_stream(self, widget):
        """Restart video stream."""
        self.stream_status.set_text("Stream: Restarting...")
        self.stop_stream()
        GLib.timeout_add(500, self.start_stream)

    def stop_stream(self):
        """Stop the video stream."""
        self.stream_running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def on_authenticate(self, webview, request, *args):
        """Handle HTTP authentication."""
        credential = WebKit2.Credential.new(
            self.username,
            self.password,
            WebKit2.CredentialPersistence.FOR_SESSION
        )
        request.authenticate(credential)
        self.logged_in = True
        return True

    def on_load_changed(self, webview, event):
        """Handle page load events."""
        if event == WebKit2.LoadEvent.FINISHED:
            self.ptz_status.set_text("PTZ: Connected")
            self.ptz_status.get_style_context().add_class("status-connected")
            # Try auto-login multiple times to handle slow-loading pages
            GLib.timeout_add(500, self.inject_auto_login_script)
            GLib.timeout_add(1500, self.inject_auto_login_script)
            GLib.timeout_add(3000, self.inject_auto_login_script)
            GLib.timeout_add(4000, self.inject_ptz_only_style)
        elif event == WebKit2.LoadEvent.STARTED:
            self.ptz_status.set_text("PTZ: Loading...")
            self.ptz_status.get_style_context().remove_class("status-connected")
            self.ptz_status.get_style_context().remove_class("status-error")

    def on_load_failed(self, webview, event, uri, error):
        """Handle load failures."""
        self.ptz_status.set_text("PTZ: Error")
        self.ptz_status.get_style_context().add_class("status-error")
        return False

    def on_delete(self, widget, event):
        """Handle window close."""
        self.stop_stream()
        Gtk.main_quit()
        return False


def main():
    win = DahuaCameraPanel()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()

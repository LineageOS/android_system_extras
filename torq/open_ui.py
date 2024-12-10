#
# Copyright (C) 2024 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Implementation taken from external/perfetto/tools/record_android_trace.
#

import webbrowser
import socketserver
import http.server
import os


class HttpHandler(http.server.SimpleHTTPRequestHandler):

  def end_headers(self):
    self.send_header("Access-Control-Allow-Origin", self.server.allow_origin)
    self.send_header("Cache-Control", "no-cache")
    super().end_headers()

  def do_GET(self):
    if self.path != "/" + self.server.expected_fname:
      self.send_error(404, "File not found")
      return
    self.server.fname_get_completed = True
    super().do_GET()

  def do_POST(self):
    self.send_error(404, "File not found")

  def log_message(self, format, *args):
    pass


def open_trace(path, origin):
  PORT = 9001
  path = os.path.abspath(path)
  os.chdir(os.path.dirname(path))
  fname = os.path.basename(path)
  socketserver.TCPServer.allow_reuse_address = True
  with socketserver.TCPServer(("127.0.0.1", PORT), HttpHandler) as httpd:
    address = (f"{origin}/#!/?url=http://127.0.0.1:"
               f"{PORT}/{fname}&referrer=open_trace_in_ui")
    webbrowser.open_new_tab(address)
    httpd.expected_fname = fname
    httpd.fname_get_completed = None
    httpd.allow_origin = origin
    while httpd.fname_get_completed is None:
      httpd.handle_request()

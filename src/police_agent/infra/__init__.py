"""Adapters onto the outside world: FastMCP, ngrok, Ollama, Gmail, Git, hardware.

Every module here wraps something this project does not control, and each one
is kept behind a narrow function so the rest of the codebase can be tested with
a substitute rather than a live account, a running daemon or a real socket.

The other rule this package carries: an outbound call to a provider goes through
`shared/gatekeeper.py`, never straight out. The gate is what applies the agreed
rate limits and the token accounting, so a second door would silently defeat
both. `ngrok_api.py` is the one exception, and it reads the ngrok agent already
running on localhost rather than any third-party API.
"""

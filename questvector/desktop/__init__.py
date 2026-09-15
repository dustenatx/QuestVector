"""Desktop shell: a pywebview window hosting the Tactical Flight Deck UI.

Spec reference: MASTER_DEVELOPER_SPEC.pdf specifies a React/Tailwind HUD
front-end, which has no Python equivalent. Per the Stage 1 blueprint
decision ("full desktop app port"), this package instead serves a themed
HTML/CSS/JS front-end (:mod:`questvector.desktop.web`) inside a native
window via `pywebview <https://pywebview.flowrl.com/>`_, bridged to the pure
Python core logic through :class:`questvector.desktop.app.Api`.
"""

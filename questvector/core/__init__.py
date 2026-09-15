"""Core, framework-independent QuestVector business logic.

Everything under this package is pure Python with no CLI, desktop, or
network-framework dependencies baked in — those live in
:mod:`questvector.cli` and :mod:`questvector.desktop`, which import from
here. This keeps business logic testable in isolation and reusable from
either surface.
"""

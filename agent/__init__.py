"""The hackathon game agent.

Layers, in dependency order (each may import from the ones before it, never after):
``adapter`` -> ``world`` -> ``pathfind`` / ``bt`` + ``strategy``.
See CLAUDE.md for the boundary each module must respect.
"""

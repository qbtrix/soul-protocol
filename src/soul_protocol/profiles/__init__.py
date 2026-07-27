# __init__.py — soul_protocol.profiles: the profile mechanism namespace.
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — namespace package for
#   Soul Protocol PROFILES. A profile is a set of conventions layered OVER the
#   unchanged core (.soul format, Soul runtime) — it adds domain semantics
#   (tagging conventions, visibility rules, role wrappers) without modifying or
#   forking any core file. First profile: profiles.game (spec/profiles/game.md).

"""Soul Protocol profiles — conventions over the unchanged core.

A *profile* is a documented set of conventions (memory tagging, visibility,
role wrappers, seams) that specializes the core ``.soul`` format and ``Soul``
runtime for a domain, without changing either. Any generic ``.soul`` reader
opens a profile-conformant soul as a perfectly valid vanilla soul;
profile-aware runtimes see more.

Available profiles:

* :mod:`soul_protocol.profiles.game` — NPC + player roles for games
  (grudges, portable reputation, the dialogue seam). Spec:
  ``spec/profiles/game.md``.
"""

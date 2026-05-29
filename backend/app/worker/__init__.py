"""ARQ background worker package (Phase B-3).

Two-module split:

* ``settings.py`` declares ``WorkerSettings`` — the class ARQ
  introspects to discover registered functions, the Redis
  connection, ``max_jobs`` etc.
* ``tasks.py`` contains the actual async task functions.

The runner is at the repository root (``backend/worker_runner.py``)
so ``python worker_runner.py`` boots the worker without needing to
remember the ``arq`` CLI syntax.
"""

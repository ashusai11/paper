# package
#
# agent1_offline/main.py does `from agent1_offline import __version__`, so the
# attribute has to exist here — without it, importing Agent 1 raises
# ImportError and the whole document lane (PDF/DOCX) cannot run.
__version__ = "1.0.0"

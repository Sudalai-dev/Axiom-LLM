"""AXIOM fine-tuning toolchain (offline, admin-run).

Turns AXIOM's own validated, grounded diagram output into a supervised dataset
for fine-tuning the local diagram model. Nothing here runs inside the serving
platform — it is invoked deliberately by an operator (see docs/FINE_TUNING.md).
"""

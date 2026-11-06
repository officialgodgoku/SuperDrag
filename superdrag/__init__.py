"""SuperDrag — instant file conversions and smart actions via liquid-glass radial dial."""
import sys

__version__ = "1.2.1"

# Backward compatibility alias for legacy imports
sys.modules.setdefault("dragshift", sys.modules[__name__])

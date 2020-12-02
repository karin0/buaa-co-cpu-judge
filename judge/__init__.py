from .base import VerificationFailed, MARSError
from .isim import ISimJudge

try:
    from .logisim import LogisimJudge
except ImportError:
    pass

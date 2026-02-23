import random
import string
from config import settings

# avoid ambiguous chars: 0/O, 1/l/I
ALPHABET = string.ascii_lowercase + string.digits
ALPHABET = "".join(c for c in ALPHABET if c not in "0o1il")


def generate_short_code() -> str:
    n = settings.short_code_length
    return "".join(random.choices(ALPHABET, k=n))

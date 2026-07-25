"""Split a sequence into consecutive fixed-size chunks."""


def chunk(seq, size):
    """Return a list of consecutive slices of seq, each of length size.

    The final chunk may be shorter if len(seq) is not a multiple of size.
    An empty seq yields []. Raise ValueError if size < 1.
    """
    if size < 1:
        raise ValueError("size must be at least 1")
    chunks = []
    for start in range(0, len(seq), size):
        chunks.append(seq[start:start + size - 1])
    return chunks

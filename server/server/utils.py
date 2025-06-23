import server.routes as routes

def dataset_hash(segments: list["routes.SegmentPostData"], source_lang, target_lang) -> str:
    """Calculate the hash of the dataset. We canonicalize the JSON representation.
    Currently use blake2b as the hashing algorithm.

    For canonical JSON, see JCS(RFC8785):
    - https://datatracker.ietf.org/doc/html/rfc8785

    Note that we take only the source and reference segments into
    account as the target segments are linked to a run, not a dataset.
    """
    import hashlib
    import iso639
    from typing import cast
    from json_canonical import canonicalize

    # make langs iso639-1
    source_lang = iso639.Language.match(source_lang).part1
    target_lang = iso639.Language.match(target_lang).part1

    data = {
        "segments": [
            {
                "src": s.src,
                "ref": s.ref if s.ref is not None else "",
            }
            for s in segments
        ],
        "source_lang": source_lang,
        "target_lang": target_lang,
    }

    canonical_json = cast(bytes, canonicalize(data))
    return hashlib.blake2b(canonical_json).hexdigest()


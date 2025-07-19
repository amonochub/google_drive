from Levenshtein import ratio

def compare_tokens(left: set[str], right: set[str]) -> list[str]:
    miss = []
    for t in left:
        if not any(ratio(t, r) > .8 for r in right):
            miss.append(t)
    return miss 
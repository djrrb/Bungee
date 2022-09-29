from fontMath.mathFunctions import factorAngle, _roundNumber

__all__ = [
    "_expandGuideline",
    "_compressGuideline",
    "_pairGuidelines",
    "_processMathOneGuidelines",
    "_processMathTwoGuidelines",
    "_roundGuidelines"
]

def _expandGuideline(guideline):
    guideline = dict(guideline)
    x = guideline.get("x")
    y = guideline.get("y")
    # horizontal
    if x is None:
        guideline["x"] = 0
        guideline["angle"] = 0
    # vertical
    elif y is None:
        guideline["y"] = 0
        guideline["angle"] = 90
    return guideline

def _compressGuideline(guideline):
    guideline = dict(guideline)
    x = guideline["x"]
    y = guideline["y"]
    angle = guideline["angle"]
    # horizontal
    if x == 0 and angle in (0, 180):
        guideline["x"] = None
        guideline["angle"] = None
    # vertical
    elif y == 0 and angle in (90, 270):
        guideline["y"] = None
        guideline["angle"] = None
    return guideline

def _pairGuidelines(guidelines1, guidelines2):
    guidelines1 = list(guidelines1)
    guidelines2 = list(guidelines2)
    pairs = []
    # name + identifier + (x, y, angle)
    _findPair(guidelines1, guidelines2, pairs, ("name", "identifier", "x", "y", "angle"))
    # name + identifier matches
    _findPair(guidelines1, guidelines2, pairs, ("name", "identifier"))
    # name + (x, y, angle)
    _findPair(guidelines1, guidelines2, pairs, ("name", "x", "y", "angle"))
    # identifier + (x, y, angle)
    _findPair(guidelines1, guidelines2, pairs, ("identifier", "x", "y", "angle"))
    # name matches
    if guidelines1 and guidelines2:
        _findPair(guidelines1, guidelines2, pairs, ("name",))
    # identifier matches
    if guidelines1 and guidelines2:
        _findPair(guidelines1, guidelines2, pairs, ("identifier",))
    # done
    return pairs

def _findPair(guidelines1, guidelines2, pairs, attrs):
    removeFromGuidelines1 = []
    for guideline1 in guidelines1:
        match = None
        for guideline2 in guidelines2:
            attrMatch = False not in [guideline1.get(attr) == guideline2.get(attr) for attr in attrs]
            if attrMatch:
                match = guideline2
                break
        if match is not None:
            guideline2 = match
            removeFromGuidelines1.append(guideline1)
            guidelines2.remove(guideline2)
            pairs.append((guideline1, guideline2))
    for removeGuide in removeFromGuidelines1:
        guidelines1.remove(removeGuide)

def _processMathOneGuidelines(guidelinePairs, ptFunc, func):
    result = []
    for guideline1, guideline2 in guidelinePairs:
        guideline = dict(guideline1)
        pt1 = (guideline1["x"], guideline1["y"])
        pt2 = (guideline2["x"], guideline2["y"])
        guideline["x"], guideline["y"] = ptFunc(pt1, pt2)
        angle1 = guideline1["angle"]
        angle2 = guideline2["angle"]
        guideline["angle"] = func(angle1, angle2) % 360
        result.append(guideline)
    return result

def _processMathTwoGuidelines(guidelines, factor, func):
    result = []
    for guideline in guidelines:
        guideline = dict(guideline)
        guideline["x"] = func(guideline["x"], factor[0])
        guideline["y"] = func(guideline["y"], factor[1])
        angle = guideline["angle"]
        guideline["angle"] = factorAngle(angle, factor, func) % 360
        result.append(guideline)
    return result

def _roundGuidelines(guidelines, digits=None):
    results = []
    for guideline in guidelines:
        guideline = dict(guideline)
        guideline['x'] = _roundNumber(guideline['x'], digits)
        guideline['y'] = _roundNumber(guideline['y'], digits)
        results.append(guideline)
    return results



if __name__ == "__main__":
    import sys
    import doctest
    sys.exit(doctest.testmod().failed)

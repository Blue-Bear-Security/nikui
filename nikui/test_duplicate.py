def process_data_cloned(data):
    """
    An exact clone of the other function.
    """
    if data:
        for item in data:
            if item.get("valid"):
                if item.get("type") == "A":
                    print("Processing A (Cloned)")
                    # Deep nesting here
                    if item.get("sub"):
                        for sub_item in item["sub"]:
                            if sub_item.get("active"):
                                if sub_item.get("priority") > 10:
                                    print("Processing High Priority Sub-item (Cloned)")
                                    return sub_item
    return data

def stuff_v2(a, b, c, d, e, f):
    """
    Long parameter list (also cloned).
    """
    pass

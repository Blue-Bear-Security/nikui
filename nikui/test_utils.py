def process_data_complex(data):
    """
    A deeply nested, poorly named function to test Nikui.
    """
    if data:
        for item in data:
            if item.get("valid"):
                if item.get("type") == "A":
                    print("Processing A")
                    # Deep nesting here
                    if item.get("sub"):
                        for sub_item in item["sub"]:
                            if sub_item.get("active"):
                                if sub_item.get("priority") > 10:
                                    print("Processing High Priority Sub-item")
                                    return sub_item
    return data

def stuff(a, b, c, d, e, f):
    """
    Long parameter list.
    """
    pass

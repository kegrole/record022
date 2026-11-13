"""Field-level diff for JSON targets."""


def flatten(obj, prefix=""):
    """Flatten nested dicts into {dotted.path: leaf_value}.

    Lists and scalars are treated as leaf values; an empty dict is a leaf.
    """
    items = {}
    if isinstance(obj, dict) and obj:
        for key in sorted(obj):
            child = "{}.{}".format(prefix, key) if prefix else str(key)
            items.update(flatten(obj[key], child))
    else:
        items[prefix] = obj
    return items


def diff_json(old_obj, new_obj):
    """Return field-level differences between two JSON objects.

    "changed" maps a field path to {"old": ..., "new": ...}; fields only
    present on one side go to "added_fields" / "removed_fields".
    """
    old_flat = flatten(old_obj)
    new_flat = flatten(new_obj)
    changed = {}
    for key in sorted(old_flat.keys() & new_flat.keys()):
        if old_flat[key] != new_flat[key]:
            changed[key] = {"old": old_flat[key], "new": new_flat[key]}
    added = {key: new_flat[key] for key in sorted(new_flat.keys() - old_flat.keys())}
    removed = {key: old_flat[key] for key in sorted(old_flat.keys() - new_flat.keys())}
    return {
        "type": "json",
        "changed": changed,
        "added_fields": added,
        "removed_fields": removed,
    }


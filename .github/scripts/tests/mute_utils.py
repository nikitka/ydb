import operator
import xml.etree.ElementTree as ET


def mute_target(node):
    failure = node.find("failure")

    if failure is None:
        return False

    skipped = ET.Element("skipped", {"message": failure.attrib["message"]})
    node.remove(failure)
    node.append(skipped)

    return True


def remove_failure(node):
    failure = node.find("failure")

    if failure is not None:
        node.remove(failure)
        return True

    return False


def op_attr(node, attr, op, value):
    v = int(node.get(attr, 0))
    node.set(attr, str(op(v, value)))


def inc_attr(node, attr, value):
    return op_attr(node, attr, operator.add, value)


def dec_attr(node, attr, value):
    return op_attr(node, attr, operator.sub, value)


def update_suite_info(root, n_remove_failures=None, n_skipped=None):
    if n_remove_failures:
        dec_attr(root, "failures", n_remove_failures)

    if n_skipped:
        inc_attr(root, "skipped", n_skipped)


def recalc_suite_info(suite):
    tests = failures = skipped = 0
    elapsed = 0.0

    for case in suite.findall("testcase"):
        a = case.attrib
        tests += 1
        elapsed += float(a["time"])
        if case.find("skipped"):
            skipped += 1
        if case.find("failure"):
            failures += 1

    suite.set("tests", str(tests))
    suite.set("failures", str(failures))
    suite.set("skipped", str(skipped))
    suite.set("time", str(elapsed))

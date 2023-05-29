#!/usr/bin/env python3
import os
import glob
import argparse
import xml.etree.ElementTree as ET


def parse_muted_list(fn):
    classes = set()
    methods = set()
    with open(fn, "r") as fp:
        for line in fp:
            if line.startswith("-"):
                line = line[1:].rstrip()
                if "::" in line:
                    cls, method = line.split("::", maxsplit=1)
                    methods.add((cls, method))
                else:
                    classes.add(line)
    return classes, methods


def jsuite_dec_failures(e: ET.Element, cnt):
    new_count = int(e.attrib["failures"]) - cnt
    e.set("failures", str(new_count))


def mute_junit(muted, folder, ok_to_patch):
    muted_cls, muted_methods = muted

    for fn in glob.glob(os.path.join(folder, "*.xml")):
        if ".patched" in fn:
            continue
        tree = ET.parse(fn)
        root = tree.getroot()
        total_muted = 0
        changed = False
        for suite in root.findall("testsuite"):
            suite_muted_fails = 0
            for case in suite.findall("testcase"):
                cls = case.attrib["classname"]
                method = case.attrib["name"]
                if cls in muted_cls or (cls, method) in muted_methods:
                    props = ET.Element("properties")

                    failure = case.find("failure")

                    if failure:
                        props.append(
                            ET.Element(
                                "property",
                                {
                                    "name": "override-failure",
                                    "value": "yes (this skip override the original test failure "
                                    "becase of our muting rules)",
                                },
                            )
                        )
                        skipped = ET.Element(
                            "skipped", {"message": failure.attrib["message"]}
                        )
                        suite_muted_fails += 1
                        case.remove(failure)
                    else:
                        skipped = ET.Element("skipped")

                    case.append(skipped)

                    props.append(
                        ET.Element(
                            "property",
                            {
                                "name": "muted",
                                "value": "according to test muting rules",
                            },
                        )
                    )
                    case.append(props)
                    changed = True

            if suite_muted_fails:
                total_muted += suite_muted_fails
                jsuite_dec_failures(suite, suite_muted_fails)

        if changed:
            jsuite_dec_failures(root, total_muted)

            if not ok_to_patch:
                print(f"{fn} needs to be patched")
            else:
                new_fn = f"{fn}.patched.xml"
                print(f"patch {fn} to {new_fn}")
                tree.write(new_fn, xml_declaration=True, encoding="UTF-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", action="store_true", default=False)
    args = parser.parse_args()

    for v in [
        "GTEST_OUTPUT",
        "Y_UNITTEST_OUTPUT",
        "Y_UNITTEST_FILTER_FILE",
    ]:
        if v not in os.environ:
            print(f"{v} environment variable is required")

    # FIXME: add gtest filter file ?
    muted = parse_muted_list(os.environ["Y_UNITTEST_FILTER_FILE"])

    if not any(muted):
        print("nothing to mute")
        return

    ytest_path = os.environ["Y_UNITTEST_OUTPUT"].replace("xml:", "")
    gtest_path = os.environ["GTEST_OUTPUT"].replace("xml:", "")

    mute_junit(muted, ytest_path, args.patch)

    if gtest_path != ytest_path:
        mute_junit(muted, ytest_path, args.patch)


if __name__ == "__main__":
    main()

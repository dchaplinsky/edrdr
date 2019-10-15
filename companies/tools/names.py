import re
import sys
import json
import argparse
from tqdm import tqdm
from functools import reduce
from itertools import permutations, product, islice, zip_longest
from operator import mul
from Levenshtein import jaro

DEBUG = False


def _compare_two_names(
    name1, name2, max_splits=7, straight_limit=0.93, smart_limit=0.95
):
    splits = name2.split(" ")

    straight_similarity = jaro(name1, name2)
    if straight_similarity > smart_limit:
        return True

    if straight_similarity > straight_limit:
        min_pair_distance = 1
        for a, b in zip_longest(name1.split(" "), splits):
            if a is not None and b is not None:
                min_pair_distance = min(jaro(a, b), min_pair_distance)

        if min_pair_distance > 0.8:
            if len(splits) > 1 and DEBUG:
                tqdm.write("Hmmm, looks like a match {}\t{}".format(name1, name2))
            return True
        else:
            if len(splits) > 1 and DEBUG:
                tqdm.write("Check if it's match: {}\t{}".format(name1, name2))

    limit = reduce(mul, range(1, max_splits + 1))

    if len(splits) > max_splits and DEBUG:
        tqdm.write("Too much permutations for {}".format(name2))

    max_similarity = max(
        jaro(name1, " ".join(opt)) for opt in islice(permutations(splits), limit)
    )

    return max_similarity > smart_limit


def full_compare(name1, name2):
    def normalize_name(s):
        return re.sub(r"\s+", " ", s.strip().replace("-", " "))

    def slugify_name(s):
        s = (
            s.replace(" ", "")
            .replace(".", "")
            .replace('"', "")
            .replace("'", "")
            .replace("’", "")
            .replace("є", "е")
            .replace("i", "и")
            .replace("ь", "")
            .replace("'", "")
            .replace('"', "")
            .replace('`', "")
            .replace("’", "")
            .replace("ʼ", "")
        )

        return re.sub(r"\d+", "", s)

    name1 = normalize_name(name1)
    name2 = normalize_name(name2)
    slugified_name1 = slugify_name(name1)
    slugified_name2 = slugify_name(name2)

    if slugified_name1 == slugified_name2:
        return True

    if slugified_name1.startswith(slugified_name2) and len(slugified_name2) >= 10:
        return True

    if slugified_name2.startswith(slugified_name1) and len(slugified_name1) >= 10:
        return True

    if jaro(slugified_name1, slugified_name2) < 0.6:
        return False

    if jaro(slugified_name1, slugified_name2) > 0.95:
        return True

    if jaro(slugified_name2, slugified_name1) > 0.95:
        return True

    if _compare_two_names(name1, name2):
        return True

    if _compare_two_names(name2, name1):
        return True

    return False


if __name__ == "__main__":
    import sys
    import csv
    from veryprettytable import VeryPrettyTable

    if len(sys.argv) > 1:
        pt = VeryPrettyTable([" ", "Positive", "Negative"])

        with open(sys.argv[1], "r") as fp:
            r = csv.DictReader(fp)

            res = {True: {True: 0, False: 0}, False: {True: 0, False: 0}}

            for l in r:
                expected = l["ground truth"].lower() in ["true", "1", "on"]
                predicted = full_compare(l["name1"], l["name2"])
                if predicted != expected:
                    print(predicted, expected, l["name1"], l["name2"])

                res[predicted][expected] += 1

        for predicted in [True, False]:
            pt.add_row(
                [
                    "Predicted positive" if predicted else "Predicted negative",
                    res[predicted][True],
                    res[predicted][False],
                ]
            )

        precision = res[True][True] / (res[True][True] + res[True][False])
        recall = res[True][True] / (res[True][True] + res[False][True])
        f1 = 2 * precision * recall / (precision + recall)

        print(pt)

        print("Precision: {:5.2f}".format(precision))
        print("Recall: {:5.2f}".format(recall))
        print("F1 score: {:5.2f}".format(f1))

    else:
        print(
            "Supply .csv file with ground truth data to calculate precision/recall/f1 metrics"
        )

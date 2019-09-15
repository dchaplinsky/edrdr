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
        return (
            s.replace(" ", "")
            .replace(".", "")
            .replace('"', "")
            .replace("'", "")
            .replace("’", "")
        )

    name1 = normalize_name(name1)
    name2 = normalize_name(name2)

    if slugify_name(name1) == slugify_name(name2):
        return True

    if jaro(slugify_name(name1), slugify_name(name2)) < 0.6:
        return False

    if _compare_two_names(name1, name2):
        if jaro(slugify_name(name1), slugify_name(name2)) > 0.85 and DEBUG:
            tqdm.write(f"compare\t{name1}\t{name2}\tTrue")

    res = _compare_two_names(name2, name1)

    if jaro(slugify_name(name1), slugify_name(name2)) > 0.85 and DEBUG:
        tqdm.write(f"compare\t{name1}\t{name2}\t{res}")
    return res


if __name__ == '__main__':
    import sys
    import csv

    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as fp:
            r = csv.reader(fp)

            res = {
                True: {True: 0, False: 0},
                False: {True: 0, False: 0},
            }

            for l in r:
                expected = l[2].lower() in ["true", "1", "on"]
                actual = full_compare(l[0], l[1])
                if actual != expected:
                    print(l[0], l[1])

                res[actual==expected][expected] += 1

        for actual in [True, False]:
            print(res[actual][actual], res[actual][not actual])

    else:
        print("Supply .csv file with ground truth data to calculate precision/recall/f1 metrics")
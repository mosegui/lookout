import argparse
import logging
import os
import subprocess
from contextlib import contextmanager
from itertools import groupby

import matplotlib.pyplot as plt
import numpy as np
import radon.complexity as cc_mod
from radon import raw
from radon.cli import Config
from radon.cli.harvest import CCHarvester, RawHarvester
from tabulate import tabulate


logger = logging.getLogger(__name__)


@contextmanager
def _temp_chdir(path):
    cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(cwd)


def get_churn_histogram(path):

    with _temp_chdir(path):
        bar = subprocess.run(["git", "log", "--format=format:", "--name-only", "."], stdout=subprocess.PIPE)
        find_repo_top_path = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE)

    repo_top_path = os.path.normpath(find_repo_top_path.stdout.decode().split("\n")[0])

    # this sorting step is necessary so that the subsequent grouping leaves all same elements contiguous
    changed_files = sorted([os.path.join(repo_top_path, os.path.normpath(event)) for event in bar.stdout.decode().split("\n") if event])

    changes_py_files = [item for item in changed_files if item.endswith('.py')]

    # some files in the repo history that do not exist anymore can still appear...
    existing_changes_py_files = [item for item in changes_py_files if os.path.exists(item)]

    return sorted([(key, len(list(group))) for key, group in groupby(existing_changes_py_files)], key=lambda x: x[0])[::-1]


def get_script_paths(path):
    sub_filepaths = [os.path.sep.join((basepath, file)) for basepath, _, files in list(os.walk(path)) for file in files]

    no_cache_filepaths = [item for item in sub_filepaths if '__pycache__' not in item]

    return [item for item in no_cache_filepaths if item.endswith('.py')]


class ModuleComplexityBrowser:
    def __init__(self, path):
        self.path = path

        with _temp_chdir(os.path.dirname(self.path)):
            analysis = self.analyze([os.path.basename(self.path)])

        self.summary = self.clean_dict(analysis)

    @staticmethod
    def analyze(paths, min='A', max='F', exclude=None, ignore=None, order='SCORE', no_assert=False, include_ipynb=False, ipynb_cells=False):

        config = Config(
            min=min.upper(),
            max=max.upper(),
            exclude=exclude,
            ignore=ignore,
            show_complexity=False,
            average=False,
            total_average=False,
            order=getattr(cc_mod, order.upper(), getattr(cc_mod, 'SCORE')),
            no_assert=no_assert,
            show_closures=False,
            include_ipynb=include_ipynb,
            ipynb_cells=ipynb_cells,
        )

        harvester = CCHarvester(paths, config)

        return harvester._to_dicts()


    def clean_dict(self, dic):

        results = dic.get(os.path.basename(self.path))

        flat_dict = {}
        flat_dict['members'] = {}

        if dic:  # skips any script that did not have any single function or class, thus yielding an empty dict
            if hasattr(results, 'keys') and 'error' in results.keys():  # some dicts are of the type {'filename.py': {'error': 'complexity error message}}
                return flat_dict
            for item in results:

                keys = ['type', 'rank', 'complexity', 'lineno']

                if item.get('type') == 'method':
                    name = f"{item.get('classname')}.{item.get('name')}"
                elif item.get('type') in ['function', 'class']:
                    name = f"{item.get('name')}"

                flat_dict['members'][name] = {key: item.get(key) for key in keys}

                flat_dict['members'][name]['length'] = item.get('endline') - item.get('lineno')

        return flat_dict


    def get_total_complexity(self):
        """"""
        module_length = np.sum([v.get('length') for v in self.summary.get('members').values() if v.get('type') in ['function', 'class']])
        complexity = np.sum([item.get('complexity')*item.get('length')/module_length for item in self.summary.get('members').values()])

        return np.round(complexity, 2)


def get_module_complexity(path):
    cc_browser = ModuleComplexityBrowser(path)
    return cc_browser.get_total_complexity()

def get_refactoring_scores(path):

    # churn
    changes_histogram = dict(get_churn_histogram(path))

    # complexity
    sub_filepaths = get_script_paths(path)
    complexity_histogram = dict([(file, get_module_complexity(file)) for file in sub_filepaths])

    common_keys = set(changes_histogram.keys()).intersection(list(complexity_histogram.keys()))

    # merge
    results = {}
    for key in common_keys:
        results[key] = {}
        results[key]['complexity'] = complexity_histogram[key]
        results[key]['churn'] = changes_histogram[key]
        results[key]['score'] = np.round(complexity_histogram[key] * changes_histogram[key], 2)

    orderable_files = [(v.get('score'), v.get('complexity'), v.get('churn'), k) for (k, v) in results.items() if np.isfinite(v.get('score'))]
    orderable_files = sorted(orderable_files, key=lambda x: x[0])[::-1]

    # not ordenable files are files with a NaN complexity, presumably due to a bug in the package dependency "ast" that ascribes to functions without
    # return the same "endline" and "lineno", thereby yielding a length of zero (Division by Zero NaN)
    not_orderable_files = [(v.get('score'), v.get('complexity'), v.get('churn'), k) for (k, v) in results.items() if np.isnan(v.get('score'))]
    not_orderable_files = sorted(not_orderable_files, key=lambda x: x[2])[::-1]

    return orderable_files + not_orderable_files


def plot_results(files_list):
    """"""
    score = [item[0] * 0.1 for item in files_list]
    complexity = [item[1] for item in files_list]
    churn = [item[2] for item in files_list]

    plt.scatter(churn, complexity, s=score)
    plt.show()

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', type=str, help='directory to analyze ')
    argparser.add_argument('-p', '--plot', action='store_true', help='present results in a plot')
    args = argparser.parse_args()

    results = get_refactoring_scores(args.path)

    print(tabulate(results, headers=['Score', 'Complexity', 'Churn', 'File'], tablefmt='orgtbl'))

    if args.plot:
        plot_results(results)


if __name__ == "__main__":

    path = r"C:\Users\mosegui\Desktop\fos4x_pkg_develop\python-packages"
    import sys
    sys.argv.append('-p')
    sys.argv.append(path)
    main()

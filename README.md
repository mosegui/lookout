# lookout
Simple tool for analyzing module complexity and churn of a  python repo for identifying refactoring hotspots.

## Usage

Install dependencies: `pip install matplotlib numpy radon tabulate`

Run on your `git` project, and see the files at the top using `less`: 

```bash
python lookout.py /path/to/project | less
```

Plots are also available:

```bash
python lookout.py /path/to/project -p
```

To get the most benefit out of this tool, you should have files of similar size.


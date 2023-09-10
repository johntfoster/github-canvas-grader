# Github Canvas Grader


[![image](https://img.shields.io/pypi/v/github-canvas-grader.svg)](https://pypi.python.org/pypi/github-canvas-grader)
[![image](https://img.shields.io/conda/vn/conda-forge/github-canvas-grader.svg)](https://anaconda.org/conda-forge/github-canvas-grader)


**Python module and command line utility for scraping Github Actions results and uploading to Canvas as grades**


-   Free software: Apache Software License 2.0
-   Documentation: https://johntfoster.github.io/github-canvas-grader


## Features

-  Scrapes results of unit tests conducted via Github Actions and uploads them to CANVAS as grades.
-  Ability to have a "multiplier" on the scores as well as a due date. This allows for increasing/decreasing scores based on when they were submitted.
-  Utility for encryping a Google client secret JSON file to allow specifying Github to EID username maps via Google Sheets.

## Installation

```
pip install github_canvas_grader
```


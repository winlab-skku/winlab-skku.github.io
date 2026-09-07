# WIn Lab website

Static site for the Wireless Intelligence Lab, Sungkyunkwan University. Hosted on GitHub Pages.

## Structure
```
index.html                Home
members/index.html        Members
publications/index.html   Publications
news/index.html           News
assets/style.css          Stylesheet
assets/photos/            Member photos  (<english-name-lowercase>.jpg, e.g. gitae-park.jpg)
assets/research/          Research-area images
data/pubs.txt             Publication list (same format as the professor's Google Site)
build.py                  Generates all HTML pages from the data above
```

## Updating
1. Edit the data:
   - Publications → `data/pubs.txt` (one paper per line under a `## Year` heading)
   - Members / alumni / news → the lists at the top of `build.py`
2. Run `python3 build.py`
3. Commit and push (or upload the changed files on github.com)

Student publication lists on the Members page are generated automatically from `data/pubs.txt`
by matching the student's English name, so keep the spelling identical in both places.
Set `SHOW_UNDERGRAD_PUBS = False` in `build.py` to hide them for undergraduates.

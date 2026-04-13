# 📦 WikiArch Dataset


## Overview

This dataset is designed to support **early-stage architectural design research**, where precedent analysis and domain knowledge play a critical role in informing design decisions.

It provides structured links between **architectural entities (e.g., buildings, projects, and places)** and their associated visual references from Wikimedia Commons. By organizing connections between textual identifiers and image resources, the dataset facilitates:

* Exploration of architectural precedents through linked visual data
* Integration into knowledge graphs representing design logic and relationships
* Retrieval-augmented systems for precedent-based design assistance

## Dataset Description

Each entry in the dataset corresponds to a Wikipedia page and includes:

* `item_name`: Title of the Wikipedia page
* `item_id`: Internal identifier
* `url`: URL of the Wikipedia page
* `images`: List of associated images, each containing:

  * `page_url`: Wikimedia Commons page URL
  * `image_id`: Unique image identifier
  * `info`: Author and license information (as provided by source)
  * `width`, `height`: Image dimensions
  * `thumbnail`: URL to a thumbnail image


## Data Format

The dataset is stored in **JSON format** as a list of objects:

```json
[
  {
    "item_name": "Example",
    "item_id": 0,
    "url": "https://en.wikipedia.org/wiki/Example",
    "images": [
      {
        "page_url": "https://commons.wikimedia.org/...",
        "image_id": "123456",
        "info": "Author / License",
        "width": 300,
        "height": 200,
        "thumbnail": "https://upload.wikimedia.org/..."
      }
    ]
  }
]
```


## License

This dataset is released under the **Creative Commons CC0 1.0 Universal (Public Domain Dedication)**.

👉 [https://creativecommons.org/publicdomain/zero/1.0/](https://creativecommons.org/publicdomain/zero/1.0/)

You are free to:

* Use, modify, and distribute the dataset
* Use it for commercial or non-commercial purposes
* Combine it with other datasets or systems

No permission is required.


## Third-Party Content Notice

This dataset includes **references** to external resources from:

* Wikipedia
* Wikimedia Commons

Important:

* This dataset **does NOT include** Wikipedia article text
* This dataset **does NOT include** image files
* It only contains **factual metadata and URLs**

### Images

* Images referenced via URLs are hosted on Wikimedia Commons
* Each image is subject to its **own license** (e.g., CC BY, CC BY-SA, Public Domain)
* Users are responsible for complying with those licenses when using the images

## Attribution (Optional but Appreciated)

Although not required under CC0, academic attribution is appreciated.

Suggested citation:

```
@article{LI2026106756,
title = {Early-stage architecture design assistance by LLMs and knowledge graphs},
journal = {Automation in Construction},
volume = {182},
pages = {106756},
year = {2026},
issn = {0926-5805},
doi = {https://doi.org/10.1016/j.autcon.2025.106756},
url = {https://www.sciencedirect.com/science/article/pii/S0926580525007964},
author = {Danrui Li and Yichao Shi and Mathew Schwartz and Mubbasir Kapadia},
}
```

## Disclaimer

This dataset is provided **“as is”**, without warranty of any kind.

The authors make no guarantees regarding:

* Accuracy or completeness of the data
* Availability or persistence of external links
* Correctness of third-party metadata


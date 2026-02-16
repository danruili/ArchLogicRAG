import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Union

VALID_IMAGE_EXTS_ORDERED = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
VALID_IMAGE_EXTS = set(VALID_IMAGE_EXTS_ORDERED)

CASE_HTML_TEMPLATE = """
<div class="case">
    <span>{index}{case_name}</span>
    <a href="">
        <img src="{db_name}/{case_name}/{asset_name}" alt="{case_name}" title="{case_name}" />
    </a>
</div>
"""

WEB_WIKIARCH_HTML_TEMPLATE = """
<div class="case">
    <span>{index}{case_name}</span>
    <a href="{url}">
        <img src="{img_url}" alt="{case_name}" title="{case_name}" width="{width}" height="{height}" />
    </a>
</div>
"""

FLASK_CASE_HTML_TEMPLATE = """
<div class="case">
    <div class="case-name">{index}{case_name}</div>
    <div class="img-holder">
        <img src="/backend-api/v2/img/{case_name}/{asset_name}" alt="{case_name}" title="{case_name}" />
    </div>
</div>
"""

HTML_STYLE = """
<script>
  document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const hide = urlParams.get('hideCaseList') === '1';

    if (hide) {
      const style = document.createElement('style');
      style.innerHTML = `.case-list { display: none !important; }`;
      document.head.appendChild(style);

      function removeCitations(el) {
        if (el.nodeType === Node.TEXT_NODE) {
          el.textContent = el.textContent.replace(/\\s?\\[\\s*\\d+(?:\\s*,\\s*\\d+)*\\s*\\]/g, '');
        } else if (el.nodeType === Node.ELEMENT_NODE) {
          for (const child of el.childNodes) {
            removeCitations(child);
          }
        }
      }

      removeCitations(document.body);
    }
  });
</script>

<style>
.case {
    display: flex;
    flex-direction: column;
    align-items: left;
    margin-top: auto;
}
.case-list{
    display: flex;
    justify-content: bottom;
    gap: 10px;
    padding-left: 40px;
    width: fit-content;
}
.case a img{
    height: 200px;
    object-fit: cover;
}
</style>
"""


def index_images_by_id(file_path: Union[str, Path]) -> Dict[str, Dict[str, Any]]:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    out: Dict[str, Dict[str, Any]] = {}

    if not isinstance(data, list):
        raise ValueError("Top-level JSON must be a list of items.")

    for item in data:
        if not isinstance(item, dict):
            continue
        item_url = item.get("url")
        images = item.get("images") or []
        if not isinstance(images, list):
            continue

        for img in images:
            if not isinstance(img, dict):
                continue
            image_id = img.get("image_id")
            if image_id is None:
                continue
            try:
                width = int(img["width"])
                height = int(img["height"])
            except (KeyError, TypeError, ValueError):
                continue

            out[str(image_id)] = {
                "width": width,
                "height": height,
                "thumbnail": img.get("thumbnail"),
                "item_url": item_url,
            }

    return out


class LinkParser:
    def __init__(self, source_dir: str, db_dir: str):
        self.source_name = os.path.basename(source_dir)
        self.source_root = Path(source_dir)
        self._asset_name_cache: dict[tuple[str, str], str | None] = {}
        self._source_candidates = [
            self.source_root,
            self.source_root / "raw",
        ]

        ref_id_mapping_path = os.path.join(db_dir, "reference", "asset_id_map.json")
        with open(ref_id_mapping_path, "r", encoding="utf-8") as f:
            self.ref_id_mapping = json.load(f)

        self.case_id_img_mapping = {}
        for asset_str in self.ref_id_mapping.values():
            case_name, asset_name = asset_str.split("|||")
            if asset_name.endswith("txt") or case_name in self.case_id_img_mapping:
                continue
            resolved = self._resolve_asset_name(case_name, asset_name)
            if resolved:
                self.case_id_img_mapping[case_name] = resolved

        web_wikiarch_meta_path = os.path.join(source_dir, "web_wikiarch_meta.json")
        if os.path.exists(web_wikiarch_meta_path):
            self.img_mapping = index_images_by_id(web_wikiarch_meta_path)
        else:
            self.img_mapping = {}

    def _candidate_asset_names(self, asset_name: str) -> list[str]:
        candidates = [asset_name]
        original_ext = Path(asset_name).suffix.lower()
        if original_ext not in VALID_IMAGE_EXTS:
            return candidates

        stem = Path(asset_name).stem
        for ext in VALID_IMAGE_EXTS_ORDERED:
            if ext == original_ext:
                continue
            candidates.append(f"{stem}{ext}")
        return candidates

    def _asset_exists(self, case_name: str, asset_name: str) -> bool:
        for root in self._source_candidates:
            if (root / case_name / asset_name).is_file():
                return True
        return False

    def _resolve_asset_name(self, case_name: str, asset_name: str) -> str | None:
        cache_key = (case_name, asset_name)
        if cache_key in self._asset_name_cache:
            return self._asset_name_cache[cache_key]

        for candidate in self._candidate_asset_names(asset_name):
            if self._asset_exists(case_name, candidate):
                self._asset_name_cache[cache_key] = candidate
                return candidate

        self._asset_name_cache[cache_key] = None
        return None

    def ref_ids_to_html(self, response_text: str, mode: str = "flask") -> str:
        index_dict = {}
        paragraphs = response_text.split("\n")
        html_paragraphs = []
        for paragraph in paragraphs:
            html_paragraph = self.__ref_ids_to_html_one_paragraph(paragraph, index_dict, mode)
            html_paragraphs.append(html_paragraph)
        return "\n".join(html_paragraphs)

    def prepare_web_content_by_paragraphs(self, response_text: str) -> list[str]:
        index_dict = {}
        paragraphs = response_text.split("\n")
        html_paragraphs = []
        for paragraph in paragraphs:
            html_paragraph = self.__ref_ids_to_html_one_paragraph(
                paragraph,
                index_dict,
                mode="web_wikiarch",
            )
            html_paragraphs.append(html_paragraph)
        return html_paragraphs

    def __ref_id_to_html(
        self,
        id_str: str,
        index_dict: dict[str, int] | None = None,
        mode: str = "flask",
    ) -> tuple[str, int]:
        clean_id = id_str.strip("[] ")

        if clean_id not in index_dict:
            index = len(index_dict)
            index_dict[clean_id] = index
        else:
            index = index_dict[clean_id]

        _, asset_id = clean_id.split("A")
        asset_str = self.ref_id_mapping[asset_id]
        case_name, asset_name = asset_str.split("|||")
        resolved_asset_name = self._resolve_asset_name(case_name, asset_name)
        if resolved_asset_name:
            asset_name = resolved_asset_name

        if asset_name.endswith("txt") and case_name in self.case_id_img_mapping:
            asset_name = self.case_id_img_mapping[case_name]

        if mode == "markdown":
            template = CASE_HTML_TEMPLATE
            return (
                template.format(
                    index=f"[{index + 1}] " if index is not None else "",
                    case_name=case_name,
                    db_name=self.source_name,
                    asset_name=asset_name,
                ),
                index + 1,
            )
        if mode == "web_wikiarch":
            img_asset_id = asset_name.split(".")[0]
            if img_asset_id in self.img_mapping:
                img_meta = self.img_mapping[img_asset_id]
                url = img_meta.get("item_url", "")
                img_url = img_meta.get("thumbnail", "")
                width = img_meta.get("width", 200)
                height = img_meta.get("height", 200)
            else:
                url = ""
                img_url = f"/backend-api/v2/img/{case_name}/{asset_name}"
                width = 200
                height = 200
            template = WEB_WIKIARCH_HTML_TEMPLATE
            return (
                template.format(
                    index=f"[{index + 1}] " if index is not None else "",
                    case_name=case_name,
                    url=url,
                    img_url=img_url,
                    width=width,
                    height=height,
                ),
                index + 1,
            )

        template = FLASK_CASE_HTML_TEMPLATE
        return (
            template.format(
                index=f"[{index + 1}] " if index is not None else "",
                case_name=case_name,
                db_name=self.source_name,
                asset_name=asset_name,
            ),
            index + 1,
        )

    def __ref_ids_to_html_one_paragraph(
        self,
        response_text: str,
        index_dict: dict,
        mode: str = "flask",
    ) -> str:
        bracket_pattern = re.compile(r" \[.*?\]")
        ref_ids = bracket_pattern.findall(response_text)
        all_cases = []
        for ref_id in ref_ids:
            if "," in ref_id:
                case_index_tuples = [
                    self.__ref_id_to_html(ref, index_dict, mode) for ref in ref_id.split(",")
                ]
                inline_indices = [str(case[1]) for case in case_index_tuples]
                cases = [case[0] for case in case_index_tuples]
                all_cases.extend(cases)
                response_text = response_text.replace(
                    ref_id,
                    f'<span class="num-link"> [{",".join(inline_indices)}]</span>',
                )
            else:
                case, case_index = self.__ref_id_to_html(ref_id, index_dict, mode)
                all_cases.append(case)
                response_text = response_text.replace(
                    ref_id, f'<span class="num-link"> [{case_index}]</span>'
                )

        if all_cases:
            response_text += f'\n\n <div class="case-list">{"\n".join(all_cases)}</div>\n'

        return response_text

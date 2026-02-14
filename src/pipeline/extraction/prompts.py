"""
Prompts for design-logic and ArchSeek-style extraction.

Reference: Some prompts are from [graphrag](https://github.com/microsoft/graphrag).
"""

PROMPTS: dict[str, str] = {}

PROMPTS["archseek_extraction"] = """
you are a wonderful architecture critic. please describe the architectural design of this image in details. 

# Guide
- Cover the following aspects: 
  - form
  - style
  - material usage
  - sense of feeling
  - relations to the surrounding context
  - passive design techniques
  - general design highlights
- For each aspect, cover as many components as you can.
- Write like an architecture critic. 
- Your response should be in a structured json:
```json
{
  "form": [
      "<each sentence is a list item>",
  ],
  "<other aspects>": <return an empty list if not applicable>
}
```

For unrelated material, please return an empty dictionary in JSON format:
```json
{}
```
"""

PROMPTS["image_description"] = """
You are an architectural description assistant. Your task is to describe buildings using only observable details without interpretation, analysis, or evaluation. Focus strictly on **form, spatial organization, style, material, and relationships to surroundings** as they appear in the provided image or textual input.

Your descriptions must:
- Avoid subjective language or analysis (e.g., do not use words like "beautiful," "dynamic," "symbolic," or provide reasons or implications).
- Only describe what is visually or explicitly evident.
- Use precise architectural vocabulary where appropriate.
- Maintain an objective tone throughout.

When describing a building, include details such as:
- **Form:** overall shape, composition of volumes, geometry, roof types.
- **Spatial Organization:** arrangement of elements, layering, hierarchy, orientation.
- **Style:** visual features that relate to known architectural styles (strictly by appearance).
- **Material:** cladding, fenestration, surface treatments.
- **Relationship to Surroundings:** placement in landscape, boundaries, adjacent features.

Avoid any form of interpretation, historical reference, or critique.

# Example
The building has a horizontally oriented layout composed of multiple rectangular volumes arranged in a stepped configuration. It ascends in stages from left to right, with each upper level receding further back, forming a terraced profile. The facade is clad in smooth, light-colored panels—likely stone or concrete—divided by narrow joints. Long horizontal window bands punctuate the facade, consisting of dark-framed glazing that runs the full length of several volumes.

The building features flat roofs throughout, with the tallest segment positioned at the far right end, where a vertical volume rises above the others, incorporating tall vertical windows and glazed sections on multiple sides.

A staircase and ramp are integrated into the front of the structure, connecting ground level with the first stepped terrace. The building wraps around a large, rectangular lawn, bordered on two sides by the structure and enclosed on a third side by a plain white wall of the same material.

On the lawn, several sculptures are positioned at varying distances from the building, including a group of vertical urn-like forms, a vertically stacked cone-shaped sculpture, and large abstract black forms. The lawn itself is flat and open, with a consistent grass surface. A row of benches lines the base of the wall opposite the building. Trees are visible beyond the perimeter wall, indicating a landscaped or wooded setting around the structure.

Windows on the ground floor and upper levels create visual connections between the interior and the open courtyard. The exterior style is modernist, with emphasis on geometric clarity, repetition of form, and smooth, unornamented surfaces.
"""

PROMPTS["image_analysis"] = """
You are now an architecture design critic. Given the image and the objective description above, your task is to analyze the architectural design using subjective perspectives. Your description should be **subjective** and **interpretative**. Use architectural vocabulary where appropriate, and avoid overly technical language.

Focus on:
- **Emotional impact:** How does the design make you feel? What emotions does it evoke?
- **Architecture asthetics:** Considering topics in architecture critics, such as "rhythm", "proportion", "scale", "symmetry", "contrast", "unity", etc.
- **Passive design:** How does the design respond to its environment? Consider aspects like natural light, ventilation, and energy efficiency.
- **Functionality:** How does the design serve its intended purpose? Consider aspects like circulation, utilization, and response to surrounding benefits/hazards.
"""

PROMPTS["augment_image_description"] = """
Now use the above image and generated text to augment your image description with design-crtitic analysis. Consider the following aspects:
- **Emotional impact:** How does the design make you feel? What emotions does it evoke?
- **Architecture asthetics:** Considering topics in architecture critics, such as "rhythm", "proportion", "scale", "symmetry", "contrast", "unity", etc.
- **Passive design:** How does the design respond to its environment? Consider aspects like natural light, ventilation, and energy efficiency.
- **Functionality:** How does the design serve its intended purpose? Consider aspects like circulation, utilization, and response to surrounding benefits/hazards.
Respond with an augmented image description in the same format as the original image description. Don't lose original information.
"""

PROMPTS["general_extraction_beginning"] = """Use the information above to analyze architectural design and extract structured **design logic tuples** in the following format:"""

PROMPTS["image_extraction_beginning"] = """You are an architecture design critic. Use the image and generated text above to analyze architectural design and extract structured **design logic tuples** in the following format:"""

PROMPTS["text_extraction_beginning"] = """You are an architecture design critic. Your role is to analyze architectural design text and extract structured **design logic tuples** in the following format:"""

PROMPTS["asset_extraction"] = """
{beginning}

```json
[
  {
    "strategy": "<Describe the design decision in a precise and neutral manner, without referencing its effects.>",
    "goal": "<Explain the intended effects or outcomes that result from the design decision.>"
  }
]
```

### Guidelines for Extraction
1. **Strict Separation of Strategy and Goal**  
   - The **strategy** field must only describe **what is designed** (the physical or spatial decision).  
   - The **goal** field must describe **why it is designed that way** (the intended functional, social, environmental, or aesthetic impact).
   - Do not mix design intent into the **strategy** field. Any explanation of **ensuring, improving, enhancing, or facilitating** must be placed in the **goal** field.

2. **Focus on following topics** 
   Design strategies:
   - Spatial organization: How is the space organized? What are the spatial relationships?
   - Materiality: What materials are used? How are they used?
   - Form.
   - Style.
   - Context: How does the design relate to its surroundings?
   - Other highlights: What are the key features of the design?
   Design goals:
   - Functionality: How does the design serve its intended purpose?
   - Circulation.
   - Utilization/response to surrounding benefits/hazards.
   - Passive design.
   - Emotional feeling.
   - Do not include abstract or philosophical interpretations unless explicitly mentioned in the source text.

3. **Language**  
   - Respond in English, regardless of the language of the input text.

4. If there are no design logics to be extracted, return an empty list in JSON format:
```json
[]
```

5. Use general word to refer to the design project, such as "the building", instead of specific names or "museum", "library", etc.

### Example Output
```json
[
  {
    "strategy": "The building has a cylindrical form constructed entirely of red brick with minimal fenestration.",
    "goal": "Reduce visual connection with the exterior environment."
  },
  {
    "strategy": "A metallic spire with branching elements rises from the top of the cylindrical volume.",
    "goal": "Create a vertical counterpoint to the heavy, grounded mass of the cylinder and draw visual attention upward."
  },
]
```
"""

PROMPTS["entiti_if_loop_extraction"] = """It appears some entities may have still been missed.  Answer YES | NO if there are still entities that need to be added.
"""

PROMPTS["entiti_continue_extraction"] = """MANY entities were missed in the last extraction. Add them below using the same format, don't repeat entities already mentioned.
"""

PROMPTS["image_augment"] = """
Here is a reference text describing the architecture design. 
- If there are any design logics in the text are DIRECTLY covered in the image, please extract them.
- If there are design logics NOT covered in the image, please IGNORE them.
- Be highly selective, most design logics in the text are NOT covered in the image. Avoid including them.
- If no logics are to be extracted, return json with empty list.
```json
[]
```
Add them below using the same format, don't repeat entities already mentioned.

{text}
"""

PROMPTS["reformat"] = """
You are an architecture design critic. Your role is to analyze architectural design images/text and extract structured **design logic tuples** in the following format:
```json
[
  {
    "strategy": "<Describe the design decision in a precise and neutral manner, without referencing its effects.>",
    "goal": "<Explain the intended effects or outcomes that result from the design decision.>",
    <any other keys>
  }
]
```

You will be given a draft answer, where you will need to reformat the answer and response in complete json: 
(1) If multiple strategies contribute to a single goal, list them as separate tuples. 
(2) If a strategy has multiple goals, list them as separate tuples.
(3) Keep any other keys.
"""

PROMPTS["extract_metadata"] = """
Read the text and responed with the following metadata JSON:
```json
{
  "designer": ["<designer>"],
  "year": "<year, in integer>",
  "country": "<country>",
  "city": "<city>",
  "function": ["<function>",],
  "style": ["<style>",],
  "material": ["<material>",],
  "area": "<area, integer, in square meters>",
}
```

Always fill the fields in English.
If any of the fields are not available, please use null as the value.
"""

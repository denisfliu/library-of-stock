---
name: Next button ordering strategy
description: How the "next" nav button orders topics within subcategories — year-based now, tag-based clustering needed later for science/concepts
type: project
---

The "next" button on study guide pages navigates to the next topic within the same subcategory. v1 ordering: chronological by year when available, alphabetical when not. Wraps around (newest → oldest).

**Why:** Most topics (people, works) have years, so chronological works. But science concepts (Alkenes, organic compounds, reactions) and philosophical movements (Empiricism) won't have years.

**How to apply:** When the yearless topic count grows (especially as we add science), revisit and implement tag-based clustering — topics sharing tags are "close" and should be adjacent. This mirrors how a textbook would group related concepts.

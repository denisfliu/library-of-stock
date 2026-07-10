---
name: Card indicator and back must agree
description: The card back should name the thing the indicator describes — if indicator is Photograph:, back is the photograph not the photographer
type: feedback
---

Card agents tend to default every back to just the creator name even when the indicator is a work type. The back should be the thing the indicator names.

**Why:** These are flashcards. If the indicator says `Photograph:`, the user is trying to identify a photograph — the back should be `Photograph Name (Creator)`, not just `Creator`. The rule "Work Name (Creator) when the card is about a specific work" was already in the docs but agents ignored it. Added a clarifying sentence: "The back should be the thing the indicator names."

**How to apply:** When reviewing card agent output, check that work-type indicators (`Photograph:`, `Exhibition:`, `Work:`, `Painting:`, etc.) have backs in `Work Name (Creator)` format, and creator-type indicators (`Artist:`, `Author:`, etc.) have backs with just the creator name. Flag mismatches during post-batch audit.

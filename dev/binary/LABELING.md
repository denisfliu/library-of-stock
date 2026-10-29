# Same-fact labelling instructions (calibration)

Each item is a pair of quizbowl clue texts, each with the answer of the
question it came from. In a tossup, "this X" / "he" / "she" refers to that
answer. In a bonus part, it refers to that part's answer.

Label each pair **same** or **different**.

**same** means both texts state the same specific fact. Examples of a
specific fact: an event, a work's detail, a plot point, a quotation, a
named relationship. The pair is still **same** when:
- the two questions have different answers because each asks about a
  different entity in that fact ("Odin hanged himself from this tree"
  → Yggdrasil vs. "This god hanged himself from Yggdrasil" → Odin);
- one text adds extra details beyond the shared fact;
- the wording is completely different.

**different** means the texts assert different facts, even if they share
a topic, an entity, a work, or vocabulary:
- "Bartók's Concerto for Orchestra parodies the Leningrad Symphony" vs.
  "Elgar's Enigma Variations has an intermezzo parodying a stutter" → different.
- "This composer wrote six string quartets" vs. "This composer's fourth
  string quartet uses Bartók pizzicato" → different (different details).
- Texts that overlap only on generic or incidental material (a
  nationality, a date, "a symphony", a common theme) → different.

When one or both texts pack several facts together, label **same** if
they share at least one specific, substantive fact. That shared fact
could point a player at either answer.

Judge only the facts. Ignore whether the answers match.

Output: a JSON array `[{"id": <id>, "label": "same" | "different"}]`
covering every item, in any order.

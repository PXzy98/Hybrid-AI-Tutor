# Answer quality of the local model on open course packs (2026-11-20)

Harness: `answer_quality.py`. Per pack, 10 public questions of `questions/<pack>.jsonl` (2 not in the material,
then concept, application and logistics in turn). For each: retrieve 4 passages (scoped to the question's
module, as the product does), build the prompt with the app's own `system_prompt` of the pack's course type and
`material_block`, answer with the lab vLLM (Qwen3.5-9B, thinking off, max 600 tokens), and judge. **The judge
is the same trusted local model** (it scores its own answers: read the scores as a check, not a neutral grade).
Pack text is real public course material, not fictional, so rule 6 keeps it away from hosted models; a first run
on 2026-11-20 used the hosted cloud model as judge and gave the same counts (CS50x grounded 1.88 there); that is
no longer the default (`--hosted-judge` needs the project's explicit permission). Judge scale: correct 0/1/2, grounded 0/1/2 (supported by the passages), unanswerable questions are
"handled" when the answer says the material does not contain it (or answers only with labelled general
knowledge). It is a single-judge, small-sample check, not a benchmark. `instructor_only/` files are not read.

| Pack | Course type / subject prompt | Answerable n | Gold file retrieved | Correct / partly / wrong | Grounded (0-2) | Unanswerable handled |
|---|---|---|---|---|---|---|
| mit_6_002_circuits | ece / engineering | 8 | 8 / 8 | 8 / 0 / 0 | 2.00 | 2 / 2 |
| harvard_cs50x | computer_science / computing | 8 | 7 / 8 | 8 / 0 / 0 | 2.00 | 2 / 2 |

Notes:

- The one CS50x row without the right file retrieved is a logistics question (cs50-24); the hosted judge of the
  first run rated its answer grounded 1 (textbook knowledge beyond the passages), the local judge 2.
- Several answers reach the 600-token limit (circ-03, circ-05, cs50-05, cs50-08): long worked answers are cut
  off at the harness limit, not by the product's limit.
- The unanswerable questions (a PID controller, PyTorch, staff office hours) were handled well: the answer
  says what the material lacks and labels the rest as general knowledge.
- S16: CS50x's manifest course type is `computer_science` and its answers use the computing prompt (the
  retrieval report `report.md` of S11 shows `ece` for CS50x and should be regenerated).
- The 9B model looks sufficient on these questions; a larger sample and an independent judge on fictional
  material would be needed to claim more. Raw rows with the judge's notes: `answer_quality.json`.
